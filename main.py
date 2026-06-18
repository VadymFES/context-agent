import sys
from storage import get_conn, get_active_goals, save_moment, add_goal, search
from capture import capture_screen
from watcher import watch
from goals import match_goals

conn = get_conn()


def on_window_change(title: str, app: str):
    goals = get_active_goals(conn)
    if not goals:
        return

    ocr_text = capture_screen()
    if len(ocr_text) < 10:
        return

    matched = match_goals(ocr_text, goals)
    if matched:
        save_moment(conn, title, app, ocr_text, matched)
        print(f"[+] {app} — {title[:60]} → goals {matched}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["add-goal"]:
        name = sys.argv[2]
        keywords = sys.argv[3:]
        gid = add_goal(conn, name, keywords)
        print(f"Goal added (id={gid})")

    elif sys.argv[1:2] == ["search"]:
        query = " ".join(sys.argv[2:])
        for r in search(conn, query):
            print(f"\n[{r['ts']}] {r['app']} — {r['title']}")
            print(f"  {r['text']}")

    else:
        print("Watching... Ctrl+C to stop")
        watch(on_window_change)