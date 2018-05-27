# GPC2Macro
Converts ConsoleTuner's GPC2 script into macro files.

This is a mostly complete release of my Python 3 script to convert combos written in GPC2 script into macro files.
I had plans to make the script more robust, but haven't gotten around to it. This script can take a full GPC2 script and
extract every combo as a maco, naming the resulting macro after it's combo counterpart.

# ASSUMPTIONS:
Combos should only have basic set_val(); and wait(); commands in them.
All params/values should not have any variables. 
All IO inputs are using the default GPC Designators. E.G. "BUTTON_1"

# KNOWN ISSUES:
  Negative floating point values produce the wrong hex code (off by a small ammount.) I haven't figured out why.
