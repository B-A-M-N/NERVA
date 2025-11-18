# Fix ASUS Zenbook Microphone (SOF Driver Issue)

## Problem
ASUS Zenbook UP6502ZD with Intel Alder Lake audio uses the `sof-hda-dsp` driver, which has **known bugs** with the digital microphone array on ASUS laptops.

## Solution: Switch to Legacy HDA Driver

The legacy `snd-hda-intel` driver works better with ASUS Zenbooks.

### Quick Fix (Temporary - Test First)

Add kernel parameter to boot with legacy driver:

1. **Edit GRUB**:
```bash
sudo nano /etc/default/grub
```

2. **Find this line**:
```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
```

3. **Change to**:
```
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash snd_hda_intel.dmic_detect=0"
```

4. **Update GRUB and reboot**:
```bash
sudo update-grub
sudo reboot
```

### After Reboot - Test

```bash
# Check which driver is loaded
cat /proc/asound/cards

# Should show: HDA-Intel instead of sof-hda-dsp

# Test microphone
arecord -d 3 test.wav
aplay test.wav
```

---

## Alternative Fix: Update SOF Firmware

If you want to keep SOF driver but fix the mic:

```bash
# Update SOF firmware
sudo apt update
sudo apt install --reinstall firmware-sof-signed

# Reboot
sudo reboot
```

---

## Alternative Fix 2: Blacklist SOF Driver

Force use of legacy driver permanently:

1. **Create blacklist file**:
```bash
sudo nano /etc/modprobe.d/blacklist-sof.conf
```

2. **Add these lines**:
```
blacklist snd_sof_pci
blacklist snd_sof_intel_hda_common
blacklist snd_sof
```

3. **Update initramfs and reboot**:
```bash
sudo update-initramfs -u
sudo reboot
```

---

## Check Current Status

```bash
# Which driver is loaded?
lsmod | grep snd

# Audio card info
cat /proc/asound/cards

# Microphone sources
pactl list sources short
```

---

## Known Issues with ASUS Zenbook + SOF

- Digital microphone array not detected
- Microphone captures silence even when unmuted
- Works fine in Windows but not Linux
- **Solution**: Use snd-hda-intel driver instead

---

## For NERVA Voice Testing

**While mic is broken, use mock mode**:

```bash
# Test voice workflow without mic
python test_voice.py --mode mock --text "what is 2+2"

# Batch test
python test_voice.py --mode batch
```

This still tests all voice features except actual microphone recording.

**After fixing mic hardware, test with**:
```bash
python test_voice_live.py
```
