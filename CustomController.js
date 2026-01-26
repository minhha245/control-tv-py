//-----------------------------------------------------------------------------
// Antigravity Custom Controller Script - Updated Mapping
//C:\Users\admin\Documents\Steinberg\Cubase\MIDI Remote\Driver Scripts\Local\HauSetup\TiengVietController
// Matching Python Controller GUI
//-----------------------------------------------------------------------------

var midiremote_api = require('midiremote_api_v1')

var deviceDriver = midiremote_api.makeDeviceDriver('HauSetup', 'TiengVietController', 'Hậu Setup Live Studio')

var midiInput = deviceDriver.mPorts.makeMidiInput()
var midiOutput = deviceDriver.mPorts.makeMidiOutput()

// --- DETECT PORT ---
deviceDriver.makeDetectionUnit().detectPortPair(midiInput, midiOutput)
    .expectInputNameContains('loopMIDI')
    .expectOutputNameContains('loopMIDI')

var surface = deviceDriver.mSurface

//-----------------------------------------------------------------------------
// HELPER FUNCTIONS
//-----------------------------------------------------------------------------
function makeFader(x, y, w, h, cc) {
    var fader = surface.makeFader(x, y, w, h)
    fader.mSurfaceValue.mMidiBinding.setInputPort(midiInput).bindToControlChange(0, cc)
    return fader
}

function makeButton(x, y, cc) {
    var btn = surface.makeButton(x, y, 2, 2)
    btn.mSurfaceValue.mMidiBinding.setInputPort(midiInput).bindToControlChange(0, cc)
    return btn
}

function makeKnob(x, y, cc) {
    var knob = surface.makeKnob(x, y, 2, 2)
    knob.mSurfaceValue.mMidiBinding.setInputPort(midiInput).bindToControlChange(0, cc)
    return knob
}

//-----------------------------------------------------------------------------
// SURFACE LAYOUT (Grid based)
// REMOVED from MIDI: LOFI (33), REMIX (34), SAVE (35)
//-----------------------------------------------------------------------------

// --- LEFT PANEL BUTTONS (Grid 0-3 X, 0-7 Y) ---
var btnDoTone = makeButton(0, 0, 30) // DÒ TONE (CC 30)
var btnLayTone = makeButton(2, 0, 31) // LẤY TONE (CC 31)

var btnNhac = makeButton(0, 2, 25) // MUTE NHẠC (CC 25)
var btnMic = makeButton(2, 2, 24) // MUTE MIC (CC 24)

var btnVang = makeButton(0, 4, 32) // VANG FX (CC 32)
var btnExtra1 = makeButton(2, 4, 40)
var btnExtra2 = makeButton(0, 6, 41)
var btnExtra3 = makeButton(2, 6, 42)
var btnExtra4 = makeButton(0, 8, 43)
var btnExtra5 = makeButton(2, 8, 44)

// LOFI, REMIX, SAVE REMOVED HERE

// --- CENTER PANEL SLIDERS (Grid 5-15 X) ---
var faderMusic = makeFader(5, 1, 2, 6, 21) // MUSIC VOL (CC 21)
var faderMic = makeFader(8, 1, 2, 6, 20) // MIC VOL (CC 20)
var faderRevL = makeFader(11, 1, 2, 6, 22) // REVERB LONG (CC 22)
var faderRevS = makeFader(14, 1, 2, 6, 23) // REVERB SHORT (CC 23)
var faderDelay = makeFader(17, 1, 2, 6, 26) // DELAY (CC 26) (Try to fit it in or adjust grid)
// Note: Grid 17 is used by Tone buttons. Let's move Delay to a new location or adjust.
// Current Center Panel: 5, 8, 11, 14. Next slot could be 17? But Right Panel starts at 17.
// Let's squeeze it or move right panel.
// Move Right Panel to 20+.
// Actually, let's put Delay at x=17 (if free) or change Right Panel.

// Let's redefine Right Panel starts at 20.
// But first, let's just insert faderDelay definition.
// Wait, I should rewrite the block to adjust coordinates if needed.
// Center Panel: 5 (Music), 8 (Mic), 11 (RevL), 14 (RevS). Each width 2. Gap 1.
// 14+2=16. So 17 is free.
// But Right Panel uses 17.
// I will move Right Panel elements to start at 20.

// REDEFINE RIGHT PANEL
var knobTone = makeKnob(20, 1, 28) // TONE VALUE (CC 28)
var knobTune = makeKnob(22, 1, 27) // TUNE (CC 27)
var knobExtra1 = makeKnob(24, 1, 45)
var knobExtra2 = makeKnob(20, 3, 46)
var knobExtra3 = makeKnob(22, 3, 47)
var knobExtra4 = makeKnob(24, 3, 48)
var knobExtra5 = makeKnob(20, 5, 49)

var btnFixMeo = makeButton(23, 6, 36) // FIX MEO (CC 36)

//-----------------------------------------------------------------------------
// HOST MAPPING (Mapping Page)
//-----------------------------------------------------------------------------
var page = deviceDriver.mMapping.makePage('Main Control')

var selectedTrack = page.mHostAccess.mTrackSelection
var mixer = selectedTrack.mMixerChannel

// 1. Mic & Music Volume/Mute
page.makeValueBinding(faderMic.mSurfaceValue, mixer.mValue.mVolume)
page.makeValueBinding(btnMic.mSurfaceValue, mixer.mValue.mMute)

page.makeValueBinding(faderMusic.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(0))
page.makeValueBinding(btnNhac.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(1))

// 2. Reverb & Delay
page.makeValueBinding(faderRevL.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(2))
page.makeValueBinding(faderRevS.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(3))
page.makeValueBinding(faderDelay.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(7))

// 3. Effects
page.makeValueBinding(btnVang.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(4))

// 4. Tone/Tune
page.makeValueBinding(knobTone.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(5))
page.makeValueBinding(knobTune.mSurfaceValue, page.mHostAccess.mFocusedQuickControls.getByIndex(6))

// 5. Extra Controls (Mapped to generic Host values for user binding)
page.makeValueBinding(btnExtra1.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(btnExtra2.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(btnExtra3.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(btnExtra4.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(btnExtra5.mSurfaceValue, mixer.mValue.mSelected)

page.makeValueBinding(knobExtra1.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(knobExtra2.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(knobExtra3.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(knobExtra4.mSurfaceValue, mixer.mValue.mSelected)
page.makeValueBinding(knobExtra5.mSurfaceValue, mixer.mValue.mSelected)
// TONE_UP and TONE_DOWN command bindings removed, now handled by knobTone value

