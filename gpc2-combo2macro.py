import os
import os.path
import re
import sys
import math
import codecs
import binascii

IS_INTERACTIVE_MODE = False
COMBO_LIST = []


class SetValParams():
    def __init__(self, button, value_raw):
        self.button = button
        self.button_hex = get_button_hex_code(self.button)
        self.value_raw = value_raw
        value_hex = get_setval_value_hex(self.value_raw)
        self.value_integer_hex = value_hex.integer_hex[2:].zfill(2)
        self.value_fraction_hex = value_hex.fraction_hex[2:].zfill(4)
        self.hex_command = generate_setval_hex_command(
                            self.button_hex,
                            self.value_integer_hex,
                            self.value_fraction_hex)


class WaitParameter():
    def __init__(self, value_raw):
        self.value_raw = value_raw
        self.value_hex = hex(int(value_raw))[2:].zfill(4)
        self.hex_command = generate_wait_hex(self.value_hex)


class SetValHexVal():
    def __init__(self, integer, fraction):
        self.integer_raw = integer
        self.fraction_raw = fraction
        self.integer_hex = int_to_hex(integer, 16)
        # TODO: Fix math, relatively accurate but negatives appear to
        # be a few decimals off. Only seems to affect negative
        # numbers greater than -100. I.E > -75.3 becomes -74.7
        # because the problem affects both the integer and the fraction.
        # I believe the problem is located inside int_to_hex().
        self.fraction_hex = int_to_hex(math.floor(int(fraction * 655.36)), 16)


class MacroHexData():
    def __init__(self):
        self.hex_list = []
        self.error_list = []

    @property
    def error_count(self):
        return len(self.error_list)

    @property
    def hex_flat(self):
        return flatten_text(''.join(self.hex_list), True)


class ComboDefinition():
    def __init__(self, combo_name, combo_definition):
        self.name = combo_name
        self.definition = combo_definition


class Define():
    def __init__(self, define_name, define_value):
        self.name = define_name
        self.value = define_value


def make_macro_file(input_file: str):
    global COMBO_LIST
    if not os.path.isfile(input_file):
        print("Error: Could not find file %s" % (input_file))
        prompt_pause_if_interactive()
        sys.exit()

    script_text = comment_remover(file_read(input_file))
    defines = get_defines(script_text)
    flat_script = flatten_text(script_text, False)
    COMBO_LIST = get_combo_list(flat_script, defines)
    for combo in COMBO_LIST:
        output_suffix = "-" + combo.name.lower() + ".gmk"
        output_file = file_path_without_ext(input_file) + output_suffix
        if os.path.isfile(output_file):
            print("\n\n")
            overwrite = ask_yes_no("Warning: Output file already exists.\n" +
                                   "Do you want to overwrite? " +
                                   "(%s)" % (output_file))
            if overwrite:
                os.remove(output_file)
            else:
                new_output_file = input("Enter a new destination now: ")
                output_file = new_output_file
        # print(combo.name + " : " + combo.definition)
        print("=========== Extracted commands from combo %s" % (combo.name))
        print(combo.definition)
        combo_to_macro_file(combo.definition, output_file)


def combo_to_macro_file(text: str, output_file: str):
    if text.count('{') > 0 or text.count('}') > 0:
        print("Error: Combo appears to have nested commands. Multiple {}" +
              " brackets found.")
        prompt_pause_if_interactive()
        sys.exit()
    macro = generate_hex_commands(text)
    macro.hex_list.append("ff")
    if macro.error_count < 1:
        bytes = binascii.unhexlify(macro.hex_flat)
        with open(output_file, 'wb') as output:
            output.write(bytes)
        print("=========== Hex commands in %s" % (output_file))
        print(macro.hex_flat)
    else:
        print("Error. Macro could not be generated. The combo contained " +
              "errors or incompatible code.")


def generate_hex_commands(text: str):
    macro = MacroHexData()
    command_list = get_command_list(text)
    for c in command_list:
        # print("command: %s" % (c))
        if is_wait_statement(c):
            wait = get_wait_time_parameter(c)
            # print(wait.hex_command)
            macro.hex_list.append(wait.hex_command)
        elif is_setval_statement(c):
            setval = get_setval_parameters(c)
            # print(setval.hex_command)
            macro.hex_list.append(setval.hex_command)
        elif is_call_statement(c):
            combo_name = get_call_combo_name(c)
            for combo in COMBO_LIST:
                if combo.name == combo_name:
                    # print("Expanding call %s" % (combo_name))
                    sub_macro = generate_hex_commands(combo.definition)
                    macro.hex_list.extend(sub_macro.hex_list)
                    macro.error_list.extend(sub_macro.error_list)
                    # print("Finished expanding call.")
        else:
            error_message = "ERROR: Unrecognized command in macro. %s" % (c)
            print(error_message)
            macro.error_list.append(error_message)
            continue
    return macro


def get_defines(text: str):
    a = []
    name = ""
    value = ""
    toggle = False
    define_complete = False
    for matches in re.findall(
            r'(?<=^\#define\s)(\w*)\s*(.*?(?=\n))',
            text,
            re.MULTILINE):
        for m in matches:
            toggle = not toggle
            if toggle:
                name = m.strip()
            else:
                define_complete = True
                value = m.strip()

            if define_complete:
                a.append(Define(name, value))
                define_complete = False
    return a


def get_combo_list(text: str, defines: str):
    combo_complete = False  # Track when ready to append to array.
    name = ""
    definition = ""
    a = []
    for matches in re.findall(r'(combo\s.*?\{)(.*?)(?=\})', text):
        for m in matches:
            if "combo " in m:
                name = m.replace("combo ", "").replace("{", "")
                name = flatten_text(name, True)
                # print(name)
            elif not is_string_empty(m) and "combo " not in m:
                # every other match should be a combo definition.
                combo_complete = True
                definition = m
                for d in defines:
                    definition = definition.replace(d.name, d.value)
                definition = flatten_text(definition, True)
                # print(definition)
            if combo_complete:
                combo_complete = False
                a.append(ComboDefinition(name, definition))
    return a


def is_wait_statement(s: str) ->bool:
    return "wait(" in s


def is_setval_statement(s: str) ->bool:
    return "set_val(" in s


def is_call_statement(s: str) ->bool:
    return "call(" in s


# Check if a string is populated or None/Empty/Whitespace
def is_string_empty(s: str) ->bool:
    return not (s and s.strip())


def flatten_text(text: str, remove_whitespace: bool) ->str:
    flat_text = ""
    for line in text.splitlines():
        flat_text += line
    if remove_whitespace:
        flat_text = flat_text.replace(" ", "")
        flat_text = flat_text.replace("\t", "")
    return flat_text


def get_command_list(s: str):
    return list(filter(None, s.split(";")))


def get_call_combo_name(s: str) ->str:
    raw = ''.join(re.findall(r'\((.*?)\)', s))
    return raw.strip()


def get_wait_time_parameter(s: str) ->str:
    raw = ''.join(re.findall(r'\((.*?)\)', s))
    return WaitParameter(raw.strip())


def get_setval_parameters(s: str) -> SetValParams:
    contents = ''.join(re.findall(r'\((.*?)\)', s))
    values = contents.split(',')
    return SetValParams(values[0], values[1])


def get_setval_value_hex(s: str):
    values = s.split('.')
    integer = clamp(int(values[0]), -100, 100)
    fraction = 0
    if integer < 100 and integer > -100:
        f = values[1]
        if len(f) == 1:
            f += "0"  # 0.5 represented as 5 should equate as 50.
        fraction = clamp(int(f), 0, 99)
    return SetValHexVal(integer, fraction)


def get_button_hex_code(s: str):
    with open('hex-button-sheet.txt') as input_file:
        for i, line in enumerate(input_file):
            if not line.strip():
                continue
            pair = [x.strip() for x in line.split(',')]
            if s == pair[0]:
                return pair[1].strip()


def generate_setval_hex_command(button: str, integer: str, fraction: str) ->str:
    template = "bbnniiffff".replace("bb", button)

    if len(integer) == 4:
        template = template.replace("nnii", integer)
    else:
        template = template.replace("nnii", "00" + integer)

    if fraction == "00":
        template = template.replace("ffff", "0000")
    else:
        template = template.replace("ffff", fraction)
    return template


def generate_wait_hex(ms: str):
    return "c00000tttt".replace("tttt", ms)


def int_to_hex(val: int, nbits: int):
    # Alternative hex conversion supporting negative numbers and different...
    # ...bit sizes 32, 64, 128 etc.
    return hex((val + (1 << nbits)) % (1 << nbits))


def clamp(n: int, minn: int, maxn: int) ->int:
    return max(min(maxn, n), minn)


def file_read(file: str) ->str:
    with open(file, 'r') as open_file:
        return open_file.read()


def file_path_without_ext(file_path: str) ->str:
    return ('.').join(file_path.split('.')[:-1])


def comment_remover(text: str) ->str:
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " "  # note: a space and not an empty string
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|\"(?:\\.|[^\\\"])*\"',
        re.DOTALL | re.MULTILINE
    )
    return re.sub(pattern, replacer, text)


def ask_yes_no(s: str) ->bool:
    while True:
        yes_choice = ['yes', 'y']
        no_choice = ['no', 'n']
        user_input = input(s + " [Y]Yes/[N]No: ").lower().strip()
        if user_input in yes_choice:
            return True
        elif user_input in no_choice:
            return False
        # else:
        #    print("Enter either [Y]Yes/[N]No")


def prompt_pause_if_interactive():
    if IS_INTERACTIVE_MODE:
        input("Press Enter to continue...")


def main(argv):
    for x in argv[1:]:
        print(x)
        if os.path.exists(x):
            make_macro_file(x)
    if len(argv) == 1:
        global IS_INTERACTIVE_MODE
        IS_INTERACTIVE_MODE = True
        print("""ConsoleTuner GPC2 combo script to macro converter.
Run script directly, or pass files as start parameters.
Working as of May 9th 2018, could break in the future.
Check that all macros open in Gtuner before putting SD card.
""")
        combo_file = input("Combo file to convert: ")
        make_macro_file(combo_file)
        print("Script completed without error!")
        prompt_pause_if_interactive()
    return


if __name__ == "__main__":
    main(sys.argv)
