<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
</head>
<body>

<h1>Overlay Typing App</h1>

<p>A Python-based <strong>draggable overlay typing tool</strong> that can automatically type text in any app. Supports <strong>Unicode characters</strong>, including French accents and special symbols, with adjustable speed and error simulation.</p>

<h2>Features</h2>
<ul>
    <li>Draggable, always-on-top overlay widget</li>
    <li>Start, Pause, Stop controls</li>
    <li>Adjustable typing <strong>speed</strong> and <strong>error percentage</strong></li>
    <li>Background writing using UI Automation when possible</li>
    <li>Fallback to foreground typing (clipboard-based for full Unicode support)</li>
    <li>Global hotkeys:
        <ul>
            <li><code>Alt + Shift + U</code> → capture target text field</li>
            <li><code>Alt + Shift + Q</code> → quit application</li>
        </ul>
    </li>
    <li>Close overlay via <strong>Escape key</strong> or <strong>✕ button</strong></li>
</ul>

<h2>Demo</h2>
<p>None for now</p>

<h2>Installation</h2>
<pre><code>git clone https://github.com/yourusername/overlay-typing-app.git
cd overlay-typing-app
pip install -r requirements.txt
</code></pre>

<p><strong>Dependencies:</strong></p>
<ul>
    <li>PyQt6</li>
    <li>pyautogui</li>
    <li>pywinauto</li>
    <li>pyperclip</li>
    <li>pynput</li>
    <li>PyGetWindow</li>
</ul>
<h2>Download</h2>
<p><a class="button" href="https://github.com/x2dat/overlay-uia-writer/blob/main/DOWNLOAD.md" target="_blank">Go to Download</a></p>
<br>
<>

<h2>Usage</h2>
<ol>
    <li>Run the overlay app: <pre><code>python overlay_typing_app.py</code></pre></li>
    <li>Drag the overlay to a convenient location.</li>
    <li>Type or paste the text you want to write automatically into the input box.</li>
    <li>Capture the target app:
        <ol>
            <li>Switch to the app you want to type in</li>
            <li>Click the text field</li>
            <li>Press <code>Alt + Shift + U</code></li>
        </ol>
    </li>
    <li>Adjust speed and error percentage sliders if desired.</li>
    <li>Press <strong>Start</strong> to begin typing. Use <strong>Pause</strong> or <strong>Stop</strong> as needed.</li>
</ol>

<h2>Notes</h2>
<ul>
    <li>For apps that support <strong>UI Automation</strong>, typing will happen in the background without focusing the target.</li>
    <li>For apps that do not support UI Automation (e.g., Google Docs in browser), the app falls back to <strong>foreground typing with clipboard-based Unicode paste</strong>.</li>
    <li>The overlay opacity is set to <strong>0.9</strong> for visibility and aesthetics.</li>
</ul>

<h2>License</h2>
<p>APACHE 2.0 License &copy;</p>

</body>
</html>
