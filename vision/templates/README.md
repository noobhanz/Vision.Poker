# Card Template Assets

The lightweight MVP recognizer supports fixed-slot card classification using rank and suit templates.

Expected structure:

```text
vision/templates/
  ranks/
    A.png
    K.png
    Q.png
    J.png
    T.png
    9.png
    ...
    2.png
  suits/
    c.png
    d.png
    h.png
    s.png
```

Templates should be grayscale-friendly crops from the top-left corner of cards for the target skin. Keep them tight around the printed symbol, with transparent or plain backgrounds avoided where possible. The detector normalizes crops before matching, but templates still need to come from the same visual family as the poker client skin.

The older full-card fallback is still supported with files such as `Ah.png`, `Kd.png`, and so on directly inside this directory.
