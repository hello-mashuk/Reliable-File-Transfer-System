# Reliable File Transfer System — Hamming(7,4) Error Detection & Correction

A Data Communication Lab project that transfers a file between two computers
over TCP/LAN/Wi-Fi, using a **Hamming(7,4) error-correcting code** implemented
from scratch, with an **application-level error simulator** and a
**checksum-based integrity check**. Comes with a clean dark-themed **Tkinter
GUI** — no terminal typing required, just install Python and run.

---

## 1. Project Overview

The sender reads a file, converts it to bits, encodes every 4 bits into a
7-bit Hamming codeword, optionally flips one intentional bit in a percentage
of those codewords (to simulate a noisy channel), and sends everything to
the receiver over a TCP socket. The receiver decodes every codeword —
detecting and correcting any single-bit error — reconstructs the exact
original file, and verifies it against a CRC32 checksum computed by the
sender.

**Important:** TCP itself already guarantees reliable, uncorrupted delivery.
We are not fighting TCP or faking network noise at the socket layer — the
"noise" here is injected deliberately at the *application* level, before
the bytes ever touch the socket, purely to give Hamming(7,4) something to
detect and fix. This is the correct way to demonstrate an error-correcting
code on top of a reliable transport.

---

## 2. Features

- Hamming(7,4) encode/decode implemented from first principles (no libraries)
- Deterministic, seedable single-bit error injection per encoded block
- CRC32 checksum-based end-to-end integrity verification
- Custom length-prefixed application protocol (no reliance on one `recv()` call returning everything)
- Clean dark-themed Tkinter GUI with a Sender tab and a Receiver tab
- Live activity log with color-coded status messages
- Works over `localhost` for single-PC testing, or real LAN/Wi-Fi for two PCs
- 21 automated unit + end-to-end tests (`test_hamming.py`)
- Zero third-party dependencies — pure Python standard library

---

## 3. Technologies Used

| Purpose                     | Library (all standard library) |
|------------------------------|--------------------------------|
| Networking                  | `socket`                       |
| Message framing              | `struct`, `json`                |
| Checksum                    | `zlib` (CRC32)                  |
| GUI                          | `tkinter`, `tkinter.ttk`         |
| Background transfer threads  | `threading`, `queue`            |
| Testing                     | `unittest`                      |

---

## 4. Project Architecture

```text
+----------+       TCP/LAN/Wi-Fi       +----------+
|          | -----------------------> |          |
|  Sender  |                          | Receiver |
|          |                          |          |
+----------+                          +----------+
     |                                      |
     v                                      v
File Processing                     Hamming Decode
     |                                      |
     v                                      v
Hamming Encode                      Error Correction
     |                                      |
     v                                      v
Error Simulation                    File Recovery
     |                                      |
     v                                      v
Checksum Calculation                Checksum Verification
```

### Folder structure

```text
reliable_file_transfer/
│
├── gui.py              # Tkinter GUI (Sender tab + Receiver tab) — run this
├── sender.py            # Core sender logic (network + encoding pipeline)
├── receiver.py           # Core receiver logic (network + decoding pipeline)
├── hamming.py            # Hamming(7,4) encode_hamming() / decode_hamming()
├── error_simulator.py     # ErrorSimulator class — application-level bit flips
├── file_handler.py        # bits<->bytes, padding, CRC32 checksum, file I/O
├── protocol.py            # Length-prefixed TCP message framing helpers
├── utils.py               # IP/port validation, byte formatting, local IP lookup
├── test_hamming.py        # 21 unit + end-to-end automated tests
├── requirements.txt        # (stdlib only — documents that fact)
└── README.md
```

Each module has exactly one job, which makes it much easier to explain
during a presentation: "this file only knows about bits and parity math",
"this file only knows about sockets", etc.

---

## 5. How Hamming(7,4) Works

We encode 4 data bits `d1 d2 d3 d4` into a 7-bit codeword by placing 3
parity bits at positions 1, 2, and 4 (the powers of two), and the data
bits at the remaining positions:

```text
Position:   1    2    3    4    5    6    7
Contents:   p1   p2   d1   p3   d2   d3   d4
```

Every position from 1–7 has a unique 3-bit binary address (1=001, 2=010,
3=011, ... 7=111). Each parity bit covers every position whose address has
the corresponding bit set:

- `p1` covers positions 1, 3, 5, 7 → `p1 = d1 ^ d2 ^ d4`
- `p2` covers positions 2, 3, 6, 7 → `p2 = d1 ^ d3 ^ d4`
- `p3` covers positions 4, 5, 6, 7 → `p3 = d2 ^ d3 ^ d4`

**Decoding:** the receiver recomputes three checks (`c1`, `c2`, `c4`) using
the exact same coverage groups. If a single bit flipped anywhere in the 7
bits, the checks won't all come out to zero — and reading them as a binary
number (`c4 c2 c1`) gives you the *exact* 1-indexed position of the bad bit
(this is called the **syndrome**). Flip that bit back, and the 4 original
data bits can be read straight out of positions 3, 5, 6, 7.

This is why Hamming(7,4) can correct any **single**-bit error per 7-bit
block, but cannot reliably correct **two or more** bit errors in the same
block — a double error produces a syndrome that looks like a *different*
single-bit error, so the decoder "corrects" the wrong bit and silently
produces incorrect data. (This is exactly why the checksum step exists — to
catch cases like that.)

---

## 6. How Error Simulation Works

`error_simulator.py`'s `ErrorSimulator` class runs **after** Hamming
encoding and **before** the data is sent over the socket. For each 7-bit
codeword, it rolls a random number; if it's below your chosen error
probability, exactly one random bit within that codeword is flipped.
Giving it a random `seed` makes a run fully reproducible — useful for a
live demo where you want to show the same "random" errors every time.

This intentionally happens above the TCP layer: TCP's own checksums and
retransmission would silently erase any corruption introduced below the
socket, so injecting noise at the socket level would prove nothing about
Hamming(7,4). Injecting it in the application data itself is the correct,
honest way to demonstrate the code.

---

## 7. How the Checksum Works

`file_handler.py` uses `zlib.crc32()` over the raw file bytes, formatted as
a fixed 8-character uppercase hex string (e.g. `7A3F91C2`). The sender
computes it once, before encoding, and sends it as part of the metadata.
The receiver recomputes it from the *reconstructed* file after Hamming
decoding and compares the two.

**Limitations:** CRC32 is a strong *accidental-corruption* detector but is
**not cryptographically secure** — it is trivial for an adversary to
construct a different file with the same CRC32 value on purpose. For this
lab (verifying that transmission + Hamming correction worked, not
defending against a malicious attacker) that's the right tool for the job.

---

## 8. How to Run the Receiver

1. Install Python 3.8+ on the receiving computer.
2. Copy the whole `reliable_file_transfer/` folder to that computer.
3. Open a terminal in that folder and run:

   ```bash
   python gui.py
   ```

4. Click the **Receiver** tab.
5. Note the **Local IP** shown at the top — you'll give this to the sender.
6. (Optional) Change the **Save Folder** — defaults to `received_files/`.
7. Set the **Listen Port** (default `5001`) and click **Start Listening**.
8. Wait — the log will show `Waiting for connection...` until the sender connects.

---

## 9. How to Run the Sender

1. Install Python 3.8+ on the sending computer.
2. Copy the whole `reliable_file_transfer/` folder to that computer.
3. Open a terminal in that folder and run:

   ```bash
   python gui.py
   ```

4. Click the **Sender** tab.
5. Enter the **Receiver IP** (the address shown on the Receiver tab of the
   other machine) and the same **Port** the receiver is listening on.
6. Click **Browse...** and pick a file.
7. (Optional) Tick **Simulate transmission errors**, set an **Error rate %**
   (e.g. `1.0` for 1%), and optionally a **Random seed** for reproducibility.
8. Click **Send File** and watch the log.

---

## 10. Testing

### On the same computer (localhost)

1. Launch `python gui.py` **twice** (two separate windows/processes).
2. In window #1 → Receiver tab → IP shown will include `127.0.0.1` usable
   locally → Start Listening on port `5001`.
3. In window #2 → Sender tab → Receiver IP = `127.0.0.1`, Port = `5001` →
   pick a file → Send File.
4. Check the `received_files/` folder next to `gui.py`.

### On two computers on the same Wi-Fi/LAN

1. Connect both computers to the **same** Wi-Fi network or LAN switch.
2. On the receiving computer: run `gui.py` → Receiver tab → note the
   **Local IP** (e.g. `192.168.1.23`) → Start Listening.
3. On the sending computer: run `gui.py` → Sender tab → Receiver IP =
   the IP you just noted → same port → Send File.
4. If the connection is refused, check:
   - Both machines are actually on the same subnet
   - The receiver's firewall allows inbound connections on that port
   - You started the receiver *before* clicking Send on the sender

### Automated tests

```bash
python -m unittest test_hamming.py -v
```

This runs 21 tests covering:
- No-error round trip for every possible 4-bit pattern
- Single-bit error injection + correction at **each** of the 7 codeword
  positions, for every possible 4-bit pattern
- Bit/byte conversion round trips and block padding edge cases
- Checksum consistency and sensitivity to corruption
- Deterministic behavior of the error simulator given a fixed seed
- Full end-to-end socket transfers over `localhost` for: a text file, a
  small binary file, an "image-like" binary file, an **empty** file, and a
  file sent **with error simulation enabled**

---

## 11. Example Terminal/Log Output

**Sender log:**
```
File: example.pdf
Original Size: 2.45 MB
Checksum: 7A3F91C2
Converting file to binary and splitting into 4-bit blocks...
Total 4-bit blocks: 5,242,880
Applying Hamming (7,4) encoding...
Encoding complete.
Error Simulation: ENABLED  (rate: 1.00%)
Errors Injected: 52,430
Connecting to receiver at 192.168.1.23:5001 ...
Connected successfully.
Sending metadata...
Sending encoded file data...
Transfer completed successfully in 4.12s.
```

**Receiver log:**
```
Server started successfully on port 5001.
Local IP (share this with the sender): 192.168.1.23
Waiting for connection...
Sender connected: 192.168.1.101
Receiving metadata...
Receiving encoded file...
Transfer complete. Received 4.28 MB.
Processing Hamming blocks...
Total Blocks: 5,242,880
Errors Detected: 52,430
Errors Corrected: 52,430
Original Checksum:  7A3F91C2
Received Checksum:  7A3F91C2
✓ FILE INTEGRITY VERIFIED
Saved to: received_files/example.pdf
Done in 3.87s.
```

---

## 12. Limitations

- Hamming(7,4) corrects **only one** bit error per 7-bit block. If two or
  more bits in the *same* block are wrong, the decoder will "correct" the
  wrong bit and the checksum comparison will (correctly) report a mismatch.
- The GUI's error simulator caps at one flipped bit per block by design —
  it cannot be used to demonstrate multi-bit corruption recovery, because
  that's outside what Hamming(7,4) is capable of.
- The whole file is read into memory at once for simplicity (fine for
  lab-scale files — documents, images, small archives). Extremely large
  files (hundreds of MB+) would benefit from chunked/streaming processing;
  see the note in `file_handler.py`.
- CRC32 is not cryptographically secure — it's an accidental-corruption
  check, not a security mechanism.
- The receiver currently accepts one connection at a time (fine for the
  lab's sender/receiver demo model).

---

## 13. Future Improvements

- Streamed, chunked processing for very large files with a live progress bar
- Support for Hamming(8,4) (SECDED — adds double-error *detection*)
- TLS-wrapped sockets for confidentiality in addition to integrity
- Multiple simultaneous receiver connections with a transfer queue
- Drag-and-drop file selection in the GUI
- A live block-by-block visualization of which blocks had errors corrected

---

