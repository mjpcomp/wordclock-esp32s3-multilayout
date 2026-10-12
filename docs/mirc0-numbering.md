# Mirc0. front: coordinates, LED indices and minute dots

Creator: [Mirc0.](https://makerworld.com/en/@Mirc0). The final period belongs to the creator name. This guide complements the exact letter diagram in include/WordClockTypes/EN10x11.mirc0.hpp.

## Three different numbering systems

- Visual columns: 0 at the left, 10 at the right, as viewed from the front.
- Upstream bit columns: 10 at the left, 0 at the right. The diagram's X means 10. These labels do not need to match LED-strip indices.
- Physical LED indices: 0-109 in the letter matrix, then 110-113 for four separate minute indicators.

The supplied maker word map and front agree with serpentine order: even rows left-to-right, odd rows right-to-left. Physical index = 11*row + (visualColumn on even rows, 10-visualColumn on odd rows). Bit column = 10-visualColumn. Hardware wiring still needs verification.

## Physical indices shown in visual left-to-right order

```text
Visual column:     0   1   2   3   4   5   6   7   8   9  10
Row 0:            0   1   2   3   4   5   6   7   8   9  10
Row 1:           21  20  19  18  17  16  15  14  13  12  11
Row 2:           22  23  24  25  26  27  28  29  30  31  32
Row 3:           43  42  41  40  39  38  37  36  35  34  33
Row 4:           44  45  46  47  48  49  50  51  52  53  54
Row 5:           65  64  63  62  61  60  59  58  57  56  55
Row 6:           66  67  68  69  70  71  72  73  74  75  76
Row 7:           87  86  85  84  83  82  81  80  79  78  77
Row 8:           88  89  90  91  92  93  94  95  96  97  98
Row 9:          109 108 107 106 105 104 103 102 101 100  99
```

## Four minute dots, separate from the letter grid

```text
LED chain: letter pixels 0..109 -> dot 1 -> dot 2 -> dot 3 -> dot 4
                                  110      111      112      113
```

This is connection order only, not a claim about the dots' physical placement. They do not form another 11-column row and do not need to align with the chart's column labels. Their actual placement can be shown later from the assembled front.

| Indicator | LED index | Lit when minute modulo 5 is |
|---|---:|---|
| Dot 1 | 110 | 1, 2, 3, 4 |
| Dot 2 | 111 | 2, 3, 4 |
| Dot 3 | 112 | 3, 4 |
| Dot 4 | 113 | 4 |

All four are off when the minute is a multiple of five. WIFI letters occupy indices 7-10 on the first row. No fifth indicator or perimeter frame is assumed. For the original chain use Normal build with MeanderRows enabled; registry/default configuration remains pending.
