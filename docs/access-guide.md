# Accessing the app — quick guide

Two ways in: **on this Mac** (localhost) and **from your iPhone or any of your
devices** (Tailscale). The server itself is always running in the background — you
never need to start anything by hand.

---

## On this Mac (localhost)

The app lives at:

| Page | URL |
|---|---|
| Dashboard | http://127.0.0.1:8787/ |
| Schedule | http://127.0.0.1:8787/schedule |
| Fuel planner | http://127.0.0.1:8787/fuel |
| Coach chat | http://127.0.0.1:8787/coach |

**Nicest setup (one-time):** open http://127.0.0.1:8787/coach in Safari, then
**File → Add to Dock…** — it becomes a standalone "Coach" app in your Dock with its
own window and icon. (Chrome: ⋮ → Cast, Save and Share → Install page as app.)

`127.0.0.1` means "this machine" — it works even with Tailscale off and never leaves
the laptop.

### Is the server running?

It should always be — launchd starts it when you log in and restarts it if it crashes.
To check or fix from Terminal:

```bash
# Is it up?
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/   # 200 = yes

# Force a restart
launchctl kickstart -k gui/$(id -u)/com.garmin-coach.web

# Watch the logs
tail -f ~/Library/Logs/garmin-coach.log
```

If the dashboard shows "Garmin session expired", run `garmin-setup` from the repo
(`~/Desktop/garmin`) and enter your Garmin login + MFA code — the app recovers on the
next page refresh, no restart needed.

---

## From your iPhone (Tailscale)

Your app's private URL — same pages, add the path you want:

> **https://anthonys-macbook-air.tail08c005.ts.net**

This only works for devices signed into *your* Tailscale account. It is not on the
public internet.

### Turning Tailscale on

- **On the Mac:** click the Tailscale icon in the menu bar (top-right) → make sure it
  says **Connected** (toggle it on if not). It normally starts at login by itself.
  If the icon is missing entirely, open Tailscale from Applications.
- **On the iPhone:** open the Tailscale app → flip the toggle to **Connected**. The
  VPN icon appears in the status bar. You can leave it on all the time — it only
  carries traffic to your own devices.

Both ends must be connected for the phone to reach the Mac.

### First time on a new phone/device

1. Install the Tailscale app and sign in with the same account
   (the one used on this Mac).
2. Open the URL above in the browser.
3. **Add to Home Screen** (iPhone: Share → Add to Home Screen) — installs the
   standalone "Coach" app with the bike icon.

### If the phone can't reach it

Check in this order:

1. **Tailscale connected on the phone?** (toggle in the Tailscale app)
2. **Mac awake?** The Mac must be on and not asleep — lid open (or clamshell with
   power + external display). Recommended: System Settings → Displays → Advanced →
   **"Prevent automatic sleeping on power adapter when the display is off"**. The
   screen may be off/locked; sleep is what breaks it.
3. **Tailscale connected on the Mac?** (menu bar icon)
4. **Server up on the Mac?** `curl` check above; `launchctl kickstart` to restart.
5. **Serve proxy still configured?** It persists across reboots, but to check or
   re-create it:
   ```bash
   alias tailscale="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
   tailscale serve status                        # should show → http://127.0.0.1:8787
   tailscale serve --bg http://127.0.0.1:8787    # re-create if missing
   ```

---

## What runs where (mental model)

```
Your iPhone ──(Tailscale VPN, HTTPS)──▶ This Mac ──▶ garmin-coach-web (background, port 8787)
Your Mac    ──(localhost, no VPN)─────▶            ├─▶ Garmin Connect (your tokens, this machine only)
                                                    └─▶ Coach chat (your Claude Code login)
```

- Nothing is public; the Tailscale account is the only "login".
- Everything — data, tokens, chat — runs on and from this Mac, so the Mac being
  **on and awake** is the one hard requirement for remote access.
