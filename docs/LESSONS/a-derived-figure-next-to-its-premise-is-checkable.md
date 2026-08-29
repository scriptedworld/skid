# 6.4 was the wrong column

`.ephemera/measure-clip-length.py` prints:

    sample      chars  generate s   audio s   ratio
    long          398        3.78     25.62    6.77
    longest      1196       11.35     76.88    6.77

`ratio` is audio seconds per second of generation. It was written down as "6.4
characters per second of audio" and copied into four documents. The speaking
rate is chars over audio, about 15.5 a second, or 155 words a minute; 6.4 would
be 64 words a minute, slower than dictation.

Both figures derived from it were wrong. FR-1.9's 300s ceiling admits about
4,660 characters, not 1,950. The generation step the watchdog must clear is
about 44 seconds, not 30, and 120s covers both, so that conclusion held on a
bad premise.

`PROJECT.md` carried the premise and the result in one sentence: 6.4 characters
per second, so 1196 characters plays for 77 seconds. 1196 over 6.4 is 187. One
division, on two numbers already side by side.

Write the unit, not the column name.
