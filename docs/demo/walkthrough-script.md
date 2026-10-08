# MuleTrace: Recordly walkthrough script (about 2.5 min)

`muletrace-demo.mp4` is the 51-second demo. This script is for the long-form demo you record yourself in **Recordly** (recordly.dev). Recordly adds the auto-zooms, smooth cursor and styled frame, so all you need to do is drive the app.

## Setup (once)
1. Start the backend: `backend/venv/bin/python -m uvicorn backend.main:app --port 8000` (run from the repo root)
2. Start the frontend: `cd frontend && npx vite`, then open http://localhost:5173 in a 1920×1080 browser window
3. In Recordly: record the **window**, turn on auto-zoom, use a soft wallpaper background with padding and shadow, and add a webcam bubble bottom-right if you're narrating.
4. Close other tabs and hide your bookmarks bar.

## Shot list

| # | Time | Do this | Say this |
|---|---|---|---|
| 1 | 0:00–0:12 | Hold on the loading screen, then the Pipeline Engine | "Money mules hide in plain sight across UPI, ATM, web and mobile. MuleTrace is an AI agent that finds them and shows its evidence." |
| 2 | 0:12–0:35 | Click **Run Full Pipeline** and let the 4 stages complete | "One click generates the transaction data, builds a unified entity graph, trains a GraphSAGE + GAT model and scores every account, in a few seconds." Point at the Test AUC and Flagged cards. |
| 3 | 0:35–1:05 | **Agent Workbench**: type *Is customer ACC-xxxxx suspicious?* (take a top account from **Account Risk**) and click **Run** | "Plain English in. The answer has a mule probability, a risk tier and an action, and each claim is cited to evidence. 2/2 citations verified." Hover over E1 and E2. |
| 4 | 1:05–1:20 | Click a structuring preset: *Find structuring patterns in the last 30 days* | "Same agent, different intent. It catches transfers engineered to stay just under the $10,000 threshold." |
| 5 | 1:20–1:45 | **Entity Graph**: click **Load Graph** and let it settle | "Accounts, devices, IPs and ATMs in one graph. Red nodes are mules, and red edges are the suspicious money paths." |
| 6 | 1:45–2:05 | **XAI Auditor** for the same account | "Why it was flagged: shared IPs, shared devices and PageRank centrality, in plain English." |
| 7 | 2:05–2:25 | **SAR Automation**: click **Generate SAR** and scroll slowly | "And one click drafts a FIU-IND Suspicious Activity Report for an analyst to review." |
| 8 | 2:25–2:35 | Back to Agent Workbench, then cut to the end card | "MuleTrace: find the mule, show the evidence, file the SAR." |

## Before you record
- The pipeline **regenerates data every run**, so account IDs and numbers change. Run it once, choose the account you'll query, and don't re-run it mid-take.
- On Pipeline Engine, the lower **Performance** card shows `AUC-ROC 0.0000` / `TEST F1 0.0000` while the top cards show the real AUC. Fix that before recording, or keep it out of frame.
- In Recordly's editor, trim the waiting time, add a 1.5× speed region over training, and put `muletrace-demo.mp4` at the start as a cold open.
