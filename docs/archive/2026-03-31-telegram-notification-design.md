# Telegram Notification Redesign

## Goal
Make the Telegram notifications highly eye-catching and organized, moving away from Discord-inherited Markdown artifacts to Telegram-native HTML features like blockquotes and monospace code blocks.

## Approach
Instead of iterating blindly over the Discord-centric `NotificationPayload.fields` without context, we will implement a custom, specialized Telegram HTML formatter inside `src/adapters/discord.py` (`_payload_to_telegram_html`).

## Design Details

1. **HTML Elements:**
   - Use `<blockquote>` blocks to group structural trading data and AI reasoning, creating a sleek left-aligned colored vertical bar in the Telegram UI.
   - Use `<code>` tags around numeric values, prices, and symbols to make them stand out in monospace.
   - Use `<pre>` tags or `<code>` blocks for AI reasoning dumps so they don't break normal formatting.

2. **Data Transformation:**
   - Map standard field keys (like "Entry", "Take Profit", "Side") to consistent, rich emojis (🎯, 💰, ⚡).
   - Automatically strip out any Discord Markdown syntax (like `**` around variables) so literal asterisks do not leak into the Telegram app.

3. **Status Differentiation:**
   - Colors/Emojis change based on whether it is a `BUY`/`WIN` (🟢/📈) or a `SELL`/`LOSS` (🔴/📉).
   - Format ALERTS, GUARDS, and CLOSE payloads similarly using blockquotes.

## Visual Spec
```html
🚨 <b>NEW SELL SIGNAL</b> 🚨
<b><a href="#">#USDJPY</a></b>

<blockquote><b>🎯 Entry:</b>       <code>159.75</code>
<b>🛑 Stop Loss:</b>   <code>159.81</code> (6.1 pips)
<b>💰 Take Profit:</b> <code>159.56</code> (18.3 pips)
<b>⚖️ Risk/Reward:</b> <code>1:3.00</code>
<b>📊 Lot Size:</b>    <code>3.27</code></blockquote>

<b>🧠 AI GUARDIAN</b>
<blockquote><b>⛔️ DECISION:</b>  NO_GO
<b>🛡️ CONFIDENCE:</b> 52.6%
<b>⚠️ REASON:</b>
<pre>Quant blocked: Score 0.53</pre></blockquote>
```
