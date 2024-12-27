from os.path import split, join, exists
from xml.etree.ElementTree import fromstring, tostring, Element, indent, ParseError
from data.data import ENDS, OBJECTS, DESIGNS, DOWNLOADS_DIR, XML_OBJ
from objects.LyXobj import LyXobj
from objects.Environment import Environment, Container


############################################### MAIN ###############################################
def one_line(file, line: str, branch: list, unknowns=None, path=None):
    unknowns = {} if type(unknowns) is not dict else unknowns
    last = branch[-1]
    if (last.is_category('Formula') or last.is_category('FormulaMacro') or last.is_command('preamble')) \
            and last.is_open() and not is_end(line, branch):
        last.text += line

    elif line.startswith('\\') or xml_command(line):
        command, category, details, text = extract_cmd(line)
        if is_end(line, branch):
            perform_end(branch, command)
        elif command == 'deeper':
            perform_deeper(file, last, unknowns, path)
        else:
            perform_new_obj(branch, unknowns, command, category, details, text, line)

    elif last.is_open():
       perform_text(last, line, path)
    else:
        last.tail += line[:-1]



def load(full_path: str):
    with open(full_path, 'r', encoding='utf8') as file:
        line = file.readline()

        while not line.startswith('\\lyxformat'):
            line = file.readline()
        fmt = line.split()[1]

        while line != f'\\begin_document\n':
            line = file.readline()
        cmd = extract_cmd(line)
        root = Environment(*cmd)
        root.set('lyxformat', fmt)

        branch = [root]
        unknowns = {}
        for line in file:
            one_line(file, line, branch, unknowns, full_path)

        if unknowns:
            print('unknown objects:', unknowns)

    return root


############################################### HELPERS ###############################################
def start_extract_cmd(line: str):
    cmd = line.split()
    new_cmd = []
    i = 0
    while i < len(cmd):
        if cmd[i].startswith('"'):
            word = []
            while i < len(cmd) and not cmd[i].endswith('"'):
                word.append(cmd[i])
                i += 1
            if i < len(cmd):
                word.append(cmd[i])
            word = ' '.join(word)
        elif cmd[i][0] in '1234567890-':
            word = []
            while i < len(cmd) and cmd[i][0] in '1234567890-' and (not cmd[i][1:] or cmd[i][1:].isnumeric()):
                word.append(cmd[i])
                i += 1
            if i < len(cmd):
                word.append(cmd[i])
            word = ' '.join(word)
        else:
            word = cmd[i]
        new_cmd.append(word)
        i += 1

    if len(new_cmd) < 3:
        new_cmd += ['', '', '']
    return new_cmd[:3]


def extract_cmd(line: str):
    command, category, details = start_extract_cmd(line)
    if command.startswith('\\'):
        command = command.replace('\\begin_', '', 1)
        command = command.replace('\\end_', '', 1)
        if not (line.startswith('\\begin{') or line.startswith('\\end{')):
            command = command.replace('\\', '', 1)
    elif command.startswith('<') and xml_command(line):
        command, category, details = xml_command(line), 'xml', ''
    else:
        raise Exception(f'invalid command: {line[:-1]}')
    if category == 'Formula' and details.startswith('$'):
        if line.endswith('$\n'):
            text = '$' + line.split('$')[-2] + '$'
        else:
            text = '$' + line.split('$')[-1]
        details = ''
    else:
        text = ''
    return command, category, details, text


def order_object(branch: list, obj):
    copy_branch = branch.copy()
    copy_branch = [str(_) + f' is open: {_.is_open()}' for _ in copy_branch]
    while branch:
        if obj.can_be_nested_in(branch[-1])[0]:
            break
        else:
            branch[-1].close()
            branch.pop()
    if not branch:
        raise Exception(f'an error occurred when ordering object {obj} in branch: {copy_branch}.')

    if len(branch) > 2 and branch[2].is_command('index'):
        branch[2].append(obj)
    elif len(branch) > 1 and branch[1].is_command('header'):
        branch[1].append(obj)
    else:
        branch[-1].append(obj)

    branch.append(obj)

    if type(obj) is Container:
        branch.append(obj[0])


def is_known_object(command: str, category: str):
    return command in OBJECTS and category in OBJECTS[command]


def xml_command(line: str):
    if line.startswith('</'):
        command = line[2:-1].split('<')[0]
    elif line.startswith('<'):
        command = line.split()[0]
    else:
        return ''
    for _ in {'<', '>', '</', '/>'}:
        command = command.replace(_, '')

    if command in XML_OBJ:
        return command
    else:
        return ''


def perform_new_obj(branch: list, unknowns: dict, command: str, category: str, details: str, text: str, line: str):
    if is_known_object(command, category):
        if details in OBJECTS[command][category]:
            if line.startswith('<'):
                line = line.replace('">', '" >')
                line = line.replace('>', '/>')
                element = fromstring(line)
                obj = Environment(element.tag, 'xml', attrib=element.attrib)
            else:
                obj = Environment(command, category, details, text)
                if obj.is_section_title():
                    obj = Container(obj)
        else:
            obj = LyXobj(command, command, category, details, text)
        order_object(branch, obj)
    else:
        if len(branch) <= 1 or not branch[1].is_command('header'):
            unknowns[command] = {category: {details: {}}}
        obj = LyXobj('unknown', command, category, details, text)
        order_object(branch, obj)


def is_end(line: str, branch: list) -> bool:
    if len(branch) > 1 and branch[1].is_command('header'):
        return line.startswith('\\end_')
    elif line.startswith('\\'):
        if line.endswith('default\n'):
            return True
        for design in ENDS:
            if line == f'\\{design} {ENDS[design]}\n':
                return True
        return line.startswith('\\end_')
    elif line.startswith('</'):
        return line.split('>')[0][2:] in XML_OBJ

    return False


def perform_end(branch: list, command: str):
    for i in range(-1, -len(branch)-1, -1):
        if branch[i].is_command(command):
            branch[i].close()
            tail = branch[len(branch)-i:]
            new_tail = []
            for _ in range(-i-1):
                branch[-1].close()
                branch.pop()

            if branch[-1].is_command('modules'):
                branch[-1].text = branch[-1].text[:-1]
            elif branch[-1].command() in DESIGNS:
                for item in tail:
                    if item.command() in DESIGNS and item.is_open():
                        new_tail.append(Environment(item.command(), item.category(), item.details()))
                if new_tail:
                    branch.pop()
                    branch.extend(new_tail)
            break


def perform_deeper(file, last, unknowns: dict, path: str):
    last.open()
    branch = [last]
    for line in file:
        if line == '\\end_deeper\n':
            break
        else:
            one_line(file, line, branch, unknowns, path)
    last.close()


def perform_options(obj: Environment, first: str, second: str, path=None):
    lst = obj.get_dict().get('options', [])
    if first in lst:
        if path is not None and first == 'filename':
            path = split(path)[0]
            new_second = second[1:] if second.startswith('"') else second
            if len(new_second) > 1 and new_second[1] != ':':  # i.e. second is not absolute path
                new_second = join(path, new_second)
                second = '"' + new_second if second.startswith('"') else new_second
            second = second.replace('/', '\\')
        obj.set(first, second)
        return True
    else:
        return False


def perform_text(last, line: str, path: str):
    dictionary = last.get_dict()
    result = False
    if 'options' in dictionary:
        options = dictionary['options']
        if line.split() and line.split()[0] in options:
            lst = line.split('"')
            if len(lst) > 1:
                for i in range(0, len(lst)//2):
                    first, second = lst[2*i][:-1], lst[2*i+1]
                    result = perform_options(last, first, second, path) or result
            else:
                lst = line.split()
                if len(lst) == 2:
                    result = perform_options(last, *lst, path)
    if not result:
        if last.is_command('modules') or last.is_command('local_layout'):
            last.text += line
        else:
            last.text += line[:-1]


#################### tables ####################


def load_table_code(file, line, index=None):
    code = line
    counter = 1
    for line in file:
        if type(index) is int:
            index += 1
        if line.startswith('<features') or line.startswith('<column'):
            if not line.endswith('/>\n'):
                line = line.replace('>', '/>')
        code += line
        if line.startswith('<lyxtabular'):
            counter += 1
        elif line.startswith('</lyxtabular'):
            counter -= 1
            if not counter:
                break
    if type(file) is list and type(index) is int:
        new_lst = file[index+1:]
        file.clear()
        file.extend(new_lst)
    return code


def one_cell(cell: Element, unknowns: dict, path: str):
    new_cell = LyXobj(cell.tag, attrib=cell.attrib)
    text = cell.text
    for e in cell:
        indent(e, space='')
        text += tostring(e, encoding='unicode')
    branch = [new_cell]
    text = text.splitlines(keepends=True)
    index = 0
    for line in text:
        one_line(text, line, branch, unknowns, path)
        index += 1
    return new_cell


def table2lyxobj(table: Element, unknowns: dict, path: str):
    new_table = LyXobj(table.tag, attrib=table.attrib)
    for item in table:
        new_item = LyXobj(item.tag, attrib=item.attrib)
        new_table.append(new_item)
        for cell in item:
            new_cell = one_cell(cell, unknowns, path)
            new_item.append(new_cell)
    return new_table


def perform_table(file, line: str, branch: list, unknowns: dict, path: str, index):
    if type(file) is list and type(index) is int:
        new_lst = file[index+1:]
        file.clear()
        file.extend(new_lst)
    code = load_table_code(file, line, index)
    try:
        table = fromstring(code)
        table = table2lyxobj(table, unknowns, path)
        branch[-1].append(table)
    except ParseError as e:
        name = 'log.xml'
        full_path = join(DOWNLOADS_DIR, name)
        while exists(full_path):
            name = '2' + name
            full_path = join(DOWNLOADS_DIR, name)
        with open(full_path, 'x', encoding='utf8') as log:
            log.write(code)
        print(f'{e}\nThe invalid code is in {full_path}.\n')
