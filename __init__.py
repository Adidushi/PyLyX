from xml.etree.ElementTree import ElementTree, tostring, indent
from subprocess import run, CalledProcessError, TimeoutExpired
from PyLyX.data.data import LYX_EXE, VERSION, CUR_FORMAT, BACKUP_DIR
from PyLyX.objects.loader import load
from PyLyX.xhtml.converter import convert
from PyLyX.xhtml.helper import CSS_FOLDER
from PyLyX.package_helper import correct_name, default_path, run_correct_brackets
from PyLyX.init_helper import *


class LyX:
    """A LyX file."""
    def __init__(self, full_path: str, writeable=True, doc_obj: Environment | None = None):
        """
        Create a LyX file object.
        :param full_path: the path where the file exists (if exists), or the path where the file will save (if not exists).
        :param writeable: do you want to write over the exists file?
        :param doc_obj: an Environment which presents a LyX document (for creating a new LyX document).
        """
        if type(full_path) is not str:
            raise TypeError(f'full_path must be a string, not {type(full_path)}.')
        self.__full_path = correct_name(full_path, '.lyx')
        self.__writeable = bool(writeable)

        if exists(self.__full_path):
            if doc_obj is not None:
                raise FileExistsError(f'file {self.__full_path} is exists.')
            self.__doc = load(self.__full_path)
            if not self.__writeable:
                self.__doc.set('original_file', self.__full_path)
        elif type(doc_obj) is Environment:
            if not doc_obj.is_command('document'):
                raise TypeError(f'invalid document object: command of {doc_obj} is not "document", but {doc_obj.command()}.')
            self.__doc = doc_obj
        else:
            raise TypeError(f'{full_path} is not valid path, and type of {doc_obj} is not {Environment.NAME}.')

    def save_as(self, path: str):
        """
        Save the LyX document object in a given path.
        """
        if type(path) is not str:
            raise TypeError(f'path must be string, not {type(path)}.')
        elif exists(path):
            raise FileExistsError(f'path {path} is exists!')
        else:
            path = correct_name(path, '.lyx')
            with open(path, 'x', encoding='utf8') as file:
                file.write(PREFIX)
                file.write(self.__doc.obj2lyx())

    def save(self, backup=True):
        """
        Save the LyX document in its current path.
        :param backup: do you want backup the old version of the LyX document?
        """
        if not self.__writeable:
            raise Exception(f'{self} is not writeable.')
        else:
            if backup:
                self.backup()
            path = self.__full_path + '_'
            if exists(path):
                remove(path)
            with open(path, 'x', encoding='utf8') as file:
                file.write(PREFIX)
                if self.__doc.get('lyxformat', CUR_FORMAT) != CUR_FORMAT:
                    run_correct_brackets(self.__doc)
                file.write(self.__doc.obj2lyx())
            if exists(self.__full_path):
                remove(self.__full_path)
            rename(self.__full_path + '_', self.__full_path)

    def backup(self) -> bool:
        """
        Backup the old version of the LyX document in the buckup directory.
        :return: True if buckup was success, False else.
        """
        if exists(self.__full_path):
            name = split(self.__full_path)[1]
            copy(self.__full_path, join(BACKUP_DIR, name))
            return True
        else:
            return False

    def get_path(self) -> str:
        """:return: the file's path."""
        return self.__full_path

    def get_doc(self) -> Environment:
        """:return: an Environment which presents a LyX document"""
        return self.__doc

    def is_writeable(self) -> bool:
        """:return: does the file can be edited by the PyLyX package."""
        return self.__writeable

    def append(self, obj: LyXobj | Environment | Container):
        """
        Append a LyXobj in the document's end.
        :param obj: a LyXobj for appending.
        :return: True if appending was success, False else.
        """
        result = rec_append(self.__doc[1], obj)
        if not result:
            print(f'an error occurred when try append {obj} to {self.__doc[1]}')
        return result

    def export(self, fmt: str, output_path='', timeout=60) -> bool:
        """
        Export the LyX document to a given format, by the built-in converter of the LyX processor.
        :param fmt: format for exporting.
        :param output_path: path for save the exporting file.
        :param timeout: maximal time for attempting to export.
        :return: True if the exporting was success, False else.
        """
        if output_path:
            fmt_ = str(fmt)
            while fmt_ and fmt[-1] in '1234567890':
                fmt_ = fmt_[:-1]
            output_path = correct_name(output_path, fmt_)
            cmd = [LYX_EXE, '--export-to', fmt, output_path, self.__full_path]
        else:
            cmd = [LYX_EXE, '--export', fmt, self.__full_path]

        export_bug_fix(True)
        try:
            run(cmd, timeout=timeout, shell=True)
            export_bug_fix(False)
            return True
        except TimeoutExpired:
            print(f'Attempting to export file "{split(self.__full_path)[1]}" took too long time.')
        except CalledProcessError as e:
            print(f'An error occurred while converting the file {self.__full_path}.\nError massage is: "{e}"')
        except FileNotFoundError:
            print(f'Make sure the path "{LYX_EXE}" is the correct lyx.exe path.')
        except Exception as e:
            print(f'An error occurred while converting the file {self.__full_path}.\nError massage is: "{e}"')
        export_bug_fix(False)
        return False

    def export2xhtml(self, output_path='', css_files=(), css_folder=CSS_FOLDER, css_copy: bool | None = None, js_files=(), js_in_head=False,
                     remove_old: bool | None = None, keep_data=False, replaces: dict | None = None):
        """
        Export the LyX document to xhtml by the PyLyX package.
        :param output_path: path for save the exporting file.
        :param css_files: paths of css files for add to the xhtml file.
        :param css_folder: path for the default css files by the PyLyX package.
        :param css_copy: do you want copy the css files to the output path?
        :param js_files: paths of js files for add to the xhtml file.
        :param js_in_head:
        :param remove_old:
        :param keep_data:
        :param replaces:
        :return:
        """
        output_path = default_path(self.__full_path, '.xhtml', output_path)
        old_file_remove(output_path, remove_old)
        root, info = convert(self.__doc, css_files, css_folder, js_files, js_in_head, keep_data, replaces)
        xhtml_style(root, output_path, css_copy, info)
        indent(root)
        with open(output_path, 'wb') as f:
            f.write(tostring(root, encoding='utf8'))
        return True

    def export2xml(self, output_path=''):
        if not output_path:
            output_path = self.__full_path.replace('.lyx', '.xml')
        else:
            output_path = correct_name(output_path, '.xml')
        xml = ElementTree(self.__doc)
        xml.write(output_path)

    def find(self, query: str | None, command='', category='', details=''):
        return rec_find(self.__doc[1], query, command, category, details)

    def find_and_replace(self, old_str, new_str, command: str | None = None, category: str | None = None, details: str | None = None, backup=True):
        if backup:
            self.backup()
        rec_find_and_replace(self.__doc, old_str, new_str, command, category, details)
        self.save()

    def reverse_rtl_links(self, backup=True) -> bool:
        if backup:
            self.backup()
        return line_functions(self, one_link)

    def update_version(self, backup=True) -> bool:
        with open(self.__full_path, 'r', encoding='utf8') as file:
            first_line = file.readline()
            if first_line.startswith(f'#LyX {VERSION}'):
                already_updated = True
            else:
                self.export('lyx')
                already_updated = False

        if VERSION == 2.4 and not already_updated:
            self.reverse_rtl_links(backup)

        return not already_updated
