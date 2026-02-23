# YouTube Key Detection - Testing Guide

## Prerequisites

1. **Install Python dependencies:**
   ```bash
   cd electron-key-detector
   pip install -r requirements.txt
   ```

2. **Install ffmpeg** (required by yt-dlp):
   - Windows: Download from https://ffmpeg.org/download.html
   - Or use chocolatey: `choco install ffmpeg`
   - Make sure `ffmpeg` is in your PATH

## Step-by-Step Testing

### 1. Start the YouTube Server

Open a terminal and run:
```bash
cd electron-key-detector
python youtube_server.py
```

You should see:
```
Starting YouTube Key Detection Server on http://localhost:5001
 * Running on http://127.0.0.1:5001
```

**Keep this terminal open!**

### 2. Start the Electron App

Open another terminal:
```bash
cd electron-key-detector
npm start
```

Or with dev tools:
```bash
npm run dev
```

### 3. Test the Detection

1. **Open DevTools** (if not already open): Press `Ctrl+Shift+I` or `F12`
2. **Navigate to a YouTube video** in the embedded browser
3. **Click the "Detect Key" button** (▶ icon in the navigation bar)
4. **Watch the Console** for detailed logs

## Expected Console Output

When you click "Detect Key", you should see:

```
🔘 Detect YouTube button clicked!
🎵 detectKeyFromYouTube() called!
=== YouTube Key Detection Started ===
Step 1: Getting webview reference...
Webview element: [object HTMLWebViewElement]
Step 2: Getting URL from webview...
Current URL: https://www.youtube.com/watch?v=...
Step 3: Checking YouTube server...
Calling window.electronAPI.checkYouTubeServer()...
YouTube server ready: true
Step 4: Updating UI to loading state...
Step 5: Sending request to download and detect...
URL being sent: https://www.youtube.com/watch?v=...
Step 6: Result received: { ... }
Step 7: YouTube detection successful!
Key: G
Scale: Major
Confidence: 85
Step 8: Updating key display...
Step 9: Adding to history...
=== YouTube Key Detection Complete ===
```

## Troubleshooting

### Issue: "YouTube server not running on port 5001"

**Solution:** Make sure you started `python youtube_server.py` in a separate terminal.

Check if the server is running:
```bash
curl http://127.0.0.1:5001/health
```

Should return: `{"status":"ok"}`

### Issue: "YouTube webview not found"

**Solution:** The webview element is missing from the HTML. Check that `index.html` has:
```html
<webview id="youtubeWebview" src="https://www.youtube.com" ...></webview>
```

### Issue: "yt-dlp error" or "ffmpeg not found"

**Solution:** 
1. Install ffmpeg: https://ffmpeg.org/download.html
2. Add ffmpeg to your system PATH
3. Restart the Python server

### Issue: Button click does nothing

**Check the console for:**
- `✅ Detect YouTube button found and event listener attached` - Button was found
- `🔘 Detect YouTube button clicked!` - Click event fired
- `🎵 detectKeyFromYouTube() called!` - Method was called

If you don't see these logs, the button might not be properly connected.

### Issue: Download takes too long

The server analyzes only the first 30 seconds of audio for speed. If it's still slow:
- Check your internet connection
- Try a shorter video
- Check Python server logs for errors

## Python Server Logs

In the Python server terminal, you should see:
```
Downloading: https://www.youtube.com/watch?v=...
Downloaded: [Song Title]
Detected: G Major (85%)
```

## Success Indicators

✅ Button changes to "Processing..." when clicked
✅ Key display shows "..." and "Downloading..."
✅ Alert shows detected key with title and confidence
✅ Key appears in the detection history
✅ Python server logs show download and detection

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ECONNREFUSED 127.0.0.1:5001` | Server not running | Start `python youtube_server.py` |
| `Not a YouTube video URL` | Not on a video page | Navigate to a YouTube video |
| `ffmpeg not found` | ffmpeg not installed | Install ffmpeg and add to PATH |
| `yt-dlp error` | Video unavailable | Try a different video |
| `Timeout` | Download too slow | Check internet connection |

## Testing with Sample Videos

Try these YouTube videos for testing:
- Short music videos (3-5 minutes)
- Popular songs with clear tonality
- Avoid very long videos (>10 minutes) for faster testing

## Next Steps

Once detection works:
1. Test with different genres of music
2. Verify accuracy against known keys
3. Test the "Send to Cubase" feature (requires Python bridge on port 9999)
