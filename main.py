import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

SUMMARIES_DIR = Path(__file__).parent / "data" / "summaries"

from storage import get_conn, get_active_goals, save_moment, add_goal, search
from capture import capture_screen
from watcher import watch
from goals import match_goals
from summarize import summarize, merge_summaries, update_user_context

conn = get_conn()

CHARACTER_LIMIT = 100_000

_session: dict = {
    "normalized": [],
    "raw": [],
    "titles": [],
    "apps": [],
    "goals": set(),
    "goal_info": [],
    "intermediate_summaries": [],
    "all_normalized": [],
    "all_titles": [],
    "all_apps": [],
    "all_goals": set(),
    "all_goal_info": [],
}


def _clear_buffer():
    _session["normalized"].clear()
    _session["raw"].clear()
    _session["titles"].clear()
    _session["apps"].clear()
    _session["goals"].clear()
    _session["goal_info"].clear()


def _clear_all():
    _clear_buffer()
    _session["intermediate_summaries"].clear()
    _session["all_normalized"].clear()
    _session["all_titles"].clear()
    _session["all_apps"].clear()
    _session["all_goals"].clear()
    _session["all_goal_info"].clear()


def _write_txt(final: dict, title: str, ts: int):
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d_%H-%M-%S")
    ai_title = final.get("title", "").strip()
    if ai_title:
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in ai_title)
        safe = safe.strip().replace(" ", "_")[:60]
        filename = f"{dt}_{safe}.txt"
    else:
        filename = f"{dt}.txt"
    path = SUMMARIES_DIR / filename

    lines = [
        f"Session: {title}",
        f"Date:    {datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    if final.get("summary"):
        lines += ["SUMMARY", "-------", final["summary"], ""]
    if final.get("main_ideas"):
        lines += ["MAIN IDEAS", "----------"]
        lines += [f"- {idea}" for idea in final["main_ideas"]]
        lines.append("")
    if final.get("important_notes"):
        lines += ["IMPORTANT NOTES", "---------------"]
        lines += [f"- {note}" for note in final["important_notes"]]
        lines.append("")
    if final.get("recommendations"):
        lines += ["RECOMMENDATIONS", "---------------"]
        lines += [f"- {rec}" for rec in final["recommendations"]]
        lines.append("")
    if final.get("links"):
        lines += ["LINKS", "-----"]
        lines += [f"- {link}" for link in final["links"]]
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[session] Saved to {path}")


def _display_and_save(final: dict, title: str, app: str, matched: list, normalized: str):
    summary_text = final.get("summary", "")
    if final.get("main_ideas"):
        summary_text += "\nMain ideas: " + "; ".join(final["main_ideas"])
    if final.get("important_notes"):
        summary_text += "\nNotes: " + "; ".join(final["important_notes"])
    if final.get("recommendations"):
        summary_text += "\nRecommendations: " + "; ".join(final["recommendations"])

    ts = int(time.time())
    save_moment(conn, title, app, normalized, matched, summary_text, final.get("links", []))
    _write_txt(final, title, ts)

    if final.get("summary"):
        print(f"[session] {final['summary']}")
    if final.get("main_ideas"):
        print(f"[session] Ideas: {'; '.join(final['main_ideas'])}")
    if final.get("important_notes"):
        print(f"[session] Notes: {'; '.join(final['important_notes'])}")
    if final.get("recommendations"):
        print(f"[session] Tips: {'; '.join(final['recommendations'])}")
    if final.get("links"):
        print(f"[session] Links: {', '.join(final['links'])}")


def _partial_flush():
    if not _session["raw"]:
        return
    combined_raw = "\n\n---\n\n".join(_session["raw"])
    title = " → ".join(dict.fromkeys(_session["titles"]))[:120]
    goal_info = list({g["id"]: g for g in _session["goal_info"]}.values())

    print(f"\n[session] Partial summarize ({len(_session['raw'])} captures, limit reached)...")
    ai = summarize(combined_raw, title, goal_info)

    if ai.get("relevant", True):
        _session["intermediate_summaries"].append(ai)
        print("[session] Partial summary stored, continuing to watch...")
    else:
        print("[session] Partial batch not relevant, continuing...")

    _session["all_normalized"].extend(_session["normalized"])
    _session["all_titles"].extend(_session["titles"])
    _session["all_apps"].extend(_session["apps"])
    _session["all_goals"].update(_session["goals"])
    _session["all_goal_info"].extend(_session["goal_info"])
    _clear_buffer()


def _flush_session():
    if _session["raw"]:
        combined_raw = "\n\n---\n\n".join(_session["raw"])
        title = " → ".join(dict.fromkeys(_session["titles"]))[:120]
        goal_info = list({g["id"]: g for g in _session["goal_info"]}.values())

        print(f"\n[session] Summarizing final {len(_session['raw'])} capture(s)...")
        ai = summarize(combined_raw, title, goal_info)

        if ai.get("relevant", True):
            _session["intermediate_summaries"].append(ai)

        _session["all_normalized"].extend(_session["normalized"])
        _session["all_titles"].extend(_session["titles"])
        _session["all_apps"].extend(_session["apps"])
        _session["all_goals"].update(_session["goals"])
        _session["all_goal_info"].extend(_session["goal_info"])

    intermediates = _session["intermediate_summaries"]
    if not intermediates:
        print("[session] Nothing relevant captured.")
        _clear_all()
        return

    all_titles = " → ".join(dict.fromkeys(_session["all_titles"]))[:120]
    app = (_session["all_apps"] or ["unknown"])[0]
    matched = list(_session["all_goals"])
    combined_normalized = "\n".join(_session["all_normalized"])

    if len(intermediates) > 1:
        print(f"\n[session] Merging {len(intermediates)} partial summaries into final conclusion...")
        final = merge_summaries(intermediates, all_titles)
    else:
        final = intermediates[0]

    _display_and_save(final, all_titles, app, matched, combined_normalized)
    all_goal_info = list({g["id"]: g for g in _session["all_goal_info"]}.values())
    update_user_context(final, all_goal_info)
    _clear_all()


def on_window_change(title: str, app: str, hwnd: int):
    goals = get_active_goals(conn)
    if not goals:
        return

    normalized, raw = capture_screen(hwnd)
    if len(normalized) < 10:
        return

    matched = match_goals(normalized, goals)
    if matched:
        _session["normalized"].append(normalized)
        _session["raw"].append(raw)
        _session["titles"].append(title)
        _session["apps"].append(app)
        _session["goals"].update(matched)
        _session["goal_info"].extend(g for g in goals if g["id"] in matched)
        print(f"[+] {app} — {title[:60]} → goals {matched}")

        if sum(len(r) for r in _session["raw"]) >= CHARACTER_LIMIT:
            _partial_flush()


if __name__ == "__main__":
    if sys.argv[1:2] == ["add-goal"]:
        args = sys.argv[2:]
        start_watch = "--watch" in args
        args = [a for a in args if a != "--watch"]
        name = args[0]
        keywords = args[1:]
        gid = add_goal(conn, name, keywords)
        print(f"Goal added (id={gid})")
        if start_watch:
            print("Watching... Ctrl+C to stop")
            try:
                watch(on_window_change)
            except KeyboardInterrupt:
                _flush_session()
                print("Stopped.")

    elif sys.argv[1:2] == ["search"]:
        query = " ".join(sys.argv[2:])
        for r in search(conn, query):
            print(f"\n[{r['ts']}] {r['app']} — {r['title']}")
            if r["summary"]:
                for line in r["summary"].splitlines():
                    print(f"  {line}")
            if r["links"]:
                print(f"  Links: {', '.join(r['links'])}")
            print(f"  ---\n  {r['text']}")

    else:
        print("Watching... Ctrl+C to stop")
        try:
            watch(on_window_change)
        except KeyboardInterrupt:
            _flush_session()
            print("Stopped.")
