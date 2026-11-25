"""Line drawings for each session and phase, as SVG path data on a 24 by 24 grid.
Drawn with a round stroke and no fill."""

SESSION_ICONS = {
    1: "M3 9h5v6H3z M10 9h4v6h-4z M16 9h5v6h-5z",                                    # text cut into tokens
    2: "M4 12h.01 M8 12h.01 M11 12h4 M13 10l2 2-2 2 M17 8h4v8h-4z",                  # ... then the next one
    3: ("M3.5 5a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0 M10.5 5a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0 "
        "M17.5 5a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0-3 0 M10 19a2 2 0 1 0 4 0a2 2 0 1 0-4 0 "
        "M5.8 6.3L11 17.2 M12 6.5V17 M18.2 6.3L13 17.2"),                            # attention converging
    4: "M12 3l9 4.5-9 4.5-9-4.5z M3 12l9 4.5 9-4.5 M3 16.5L12 21l9-4.5",             # stacked layers
    5: ("M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z "
        "M8.5 8.5h.01 M15.5 8.5h.01 M12 12h.01 M8.5 15.5h.01 M15.5 15.5h.01"),       # dice, for sampling
    6: "M4 12a8 8 0 1 0 16 0a8 8 0 1 0-16 0 M8 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0 M12 12h.01",   # target
    7: "M4 4v16h16 M9 14h.01 M13 10h.01 M17 7h.01 M15 15h.01 M8 9h.01",              # points on axes
    8: ("M13 3H6v18h5 M13 3l5 5v3 M13 3v5h5 M9 12h4 M9 15h2 "
        "M13.5 17a3 3 0 1 0 6 0a3 3 0 1 0-6 0 M18.7 19.2L21 21.5"),                  # document and magnifier
    9: ("M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91"
        "a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"),           # wrench
    10: ("M4 12a8 8 0 0 1 13.7-5.7L20 8.5 M20 4v4.5h-4.5 M20 12a8 8 0 0 1-13.7 5.7L4 15.5 "
         "M4 20v-4.5h4.5 M12 12h.01"),                                               # loop
    11: "M12 3l8 3v6c0 4.5-3.2 8.3-8 9.5-4.8-1.2-8-5-8-9.5V6z M9 12l2 2 4-4",        # shield with a tick
    12: ("M4 6a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M16 6a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M10 18a2 2 0 1 0 4 0a2 2 0 1 0-4 0 "
         "M8 6h8 M7 7.8l4 8.4 M17 7.8l-4 8.4"),                                      # connected graph
    13: ("M4 7h10 M18 7h2 M4 12h4 M12 12h8 M4 17h12 M14 7a2 2 0 1 0 4 0a2 2 0 1 0-4 0 "
         "M8 12a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M16 17a2 2 0 1 0 4 0a2 2 0 1 0-4 0"),    # sliders
    14: "M3 21l6-9 4 5 3-4 5 8z M9 12V4 M9 4h6l-2 2.5 2 2.5H9",                      # flag on a summit
}

PHASE_ICONS = {
    1: "M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12l8-4.5 M12 12v9 M12 12L4 7.5",          # a building block
    2: ("M7 9h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2z M12 9V5.5 "
        "M9.5 13.5h.01 M14.5 13.5h.01 M9.5 16.5h5 M11 4.5a1 1 0 1 0 2 0a1 1 0 1 0-2 0"),   # the agent
}

LOCK_ICON = "M8 11V8a4 4 0 0 1 8 0v3 M6 11h12v9H6z"
