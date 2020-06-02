'''
Converting HTML to LaTeX for typesetting consoles (new version).

The newer version is more concise and tends to create more compact LaTeX code.

Author: Alan Xiang (www.alanshawn.com)
'''

import copy
from html.parser import HTMLParser
from colour import Color
import wx

# manages color conversion between HTML and LaTeX
class ColorManager:

    def __init__(self):
        self.color_dict = dict()
        self.all_colors = []
        self.hashed_colors = []

    def add_color(self, color_s):
        assert color_s not in self.color_dict
        color = Color(color_s)

        # check if this color is already defined
        try:
            self.all_colors.index(color)
        except ValueError:
            next_ind = len(self.all_colors)
            self.all_colors.append(color)
            self.hashed_colors.append(self._hash_color_name(color))
            self.color_dict[color_s] = next_ind

    # hash color names for latex
    def _hash_color_name(self, clr_obj):
        clr_hex_string = clr_obj.get_hex_l()[1:].lower()
        hashed_hex = ''
        for s in clr_hex_string:
            if ord('0') <= ord(s) <= ord('9'):
                hashed_hex += chr(int(s) + ord('a'))
            elif ord('a') <= ord(s) <= ord('f'):
                hashed_hex += chr(ord('k') + ord(s) - ord('a'))
            else:
                raise RuntimeError('invalid character encountered in color string \'{}\''.format(clr_hex_string))
        return 'clr' + hashed_hex

    def get_hashed_color(self, color_s):
        assert color_s in self.color_dict
        return self.hashed_colors[self.color_dict[color_s]]

    def getadd_hashed_color(self, color_s):
        if color_s not in self.color_dict:
            self.add_color(color_s)
        return self.get_hashed_color(color_s)

    def generate_latex_color_definition(self):
        def_list = []
        for i in range(len(self.all_colors)):
            def_list.append(r'\definecolor{%s}{HTML}{%s}' % (self.hashed_colors[i], self.all_colors[i].get_hex_l()[1:]))
        return ''.join(def_list)

latex_special_chars = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\^{}',
    '\\': r'\textbackslash{}',
    '\n': '\\newline%\n',
    '-': r'{-}',
    '\xA0': '~',  # Non-breaking space
    '[': r'{[}',
    ']': r'{]}',
    '*' : r'\ctmstar{}',
    ' ' : r'\space{}'
}

# marks unicode characters that may need to be escaped in some TeX engine
class UnicodeChar:
    def __init__(self, c):
        assert len(c) == 1
        self.c = c

# converts stylized string into LaTeX
# the styles are represented using dictionaries
class LaTeXify:

    empty_style = dict()
    def __init__(self, **kwargs):
        self.current_style = LaTeXify.empty_style
        self.current_raw_data = []
        self.stylized_data = []
        self.color_manager = ColorManager()

        self.escape_unicode = kwargs.get('escape_unicode', True)
        self.unicode_escape_mode = kwargs.get('unicode_escape_mode', 'dec')

    def set_style(self, style_dict):
        # Do something if the new style is different from current style
        if style_dict != self.current_style:
            self._flush_current_raw_data()
            self.current_style = style_dict
            self.current_raw_data = []

    def append_data(self, data):
        result = []
        # flag unicode characters
        for s in data:
            if ord(s) > 127:
                result.append(UnicodeChar(s))
            else:
                result.append(s)
        self.current_raw_data.extend(result)

    def dumps(self):
        if len(self.current_raw_data) > 0:
            self._flush_current_raw_data()

        body = ''
        for stylized_d in self.stylized_data:
            body += self._latex_stylize(stylized_d)

        color_def = self.color_manager.generate_latex_color_definition()

        content_list = [
            '{',
            r'\setlength{\fboxsep}{0pt}',
            color_def,
            r'\begin{tcbconsole}',
            body.strip(),
            r'\end{tcbconsole}',
            '}'
        ]

        return '\n'.join(filter(lambda x : len(x) > 0, content_list))

    def _flush_current_raw_data(self):
        stylized = {
            'style': copy.copy(self.current_style),
            'data': copy.copy(self.current_raw_data)
        }
        self.stylized_data.append(stylized)

    # group consecutive ASCII characters/UnicodeChar into list of lists
    def _group_characters_by_class(self, data):
        result = []
        if len(data) == 0:
            return result

        current_list = []
        last_type = type(data[0])
        for obj in data:
            if type(obj) == last_type:
                current_list.append(obj)
            else:
                result.append(current_list)
                last_type = type(obj)
                current_list = [obj]

        if len(current_list) > 0:
            result.append(current_list)

        return result

    # extract characters out from UnicodeChar class
    # this is used when there is no need to escape them
    def _extract_unicodechar(self, data):
        ret = ''
        for s in data:
            if isinstance(s, str):
                ret += s
            elif isinstance(s, UnicodeChar):
                ret += s.c
            else:
                raise RuntimeError('unknown character type \'{}\' encountered in stylized data'.format(type(s)))
        return ret

    def _surround_with_listing_escape(self, s):
        return '%*{}*)'.format(s)

    def _escape_unicodechar(self, uc):
        assert isinstance(uc, UnicodeChar)

        if ord(uc.c) == 0xfffd:
        	return r'\unknownunicodesymbol'
        
        if self.unicode_escape_mode == 'hex':
            return r'\unichar{{"{:x}}}'.format(ord(uc.c))
        elif self.unicode_escape_mode == 'dec':
            return r'\unichar{{{}}}'.format(ord(uc.c))
        else:
            raise RuntimeError('unknown UnicodeChar escape mode \'{}\''.format(self.unicode_escape_mode))

    def _escape_latex(self, data):
        result = []
        for obj in data:
            if isinstance(obj, str):
                result.append(latex_special_chars.get(obj, obj))
            elif isinstance(obj, UnicodeChar):
                if self.escape_unicode:
                    result.append(self._escape_unicodechar(obj))
                else:
                    result.append(obj.c)
            else:
                raise RuntimeError('unknown character type \'{}\' encountered in stylized data'.format(type(obj)))
        return ''.join(result)

    def _latex_stylize(self, stylized_d):
        ret = ''
        if stylized_d['style'] == LaTeXify.empty_style:
            # no style
            if self.escape_unicode:
                grouped_char = self._group_characters_by_class(stylized_d['data'])
                for group in grouped_char:
                    assert len(group) > 0
                    if isinstance(group[0], str):
                        ret += ''.join(group)
                    elif isinstance(group[0], UnicodeChar):
                        escaped_char = [self._escape_unicodechar(uc) for uc in group]
                        ret += self._surround_with_listing_escape(''.join(escaped_char))
                    else:
                        raise RuntimeError('unknown character type \'{}\' encountered in stylized data'.format(type(group[0])))
            else:
                ret = ''.join(self._extract_unicodechar(stylized_d['data']))
        else:
            cmd_prefix = []
            cmd_suffix = []
            # has style
            # so far the values of these styles are not processed, we just check if they are present in the dictionary
            styles = stylized_d['style']
            if 'background-color' in styles:
                cmd_prefix.append(r'\smash{\colorbox{%s}{\ctmstrut{}' % self.color_manager.getadd_hashed_color(styles['background-color']))
                cmd_suffix.insert(0, '}}')
            if 'font-weight' in styles:
                cmd_prefix += r'\bfseries{}'
            if 'color' in styles:
                cmd_prefix.append('\color{%s}' % self.color_manager.getadd_hashed_color(styles['color']))
            if 'text-decoration-style' in styles:
                cmd_prefix.append(r'\underline{')
                cmd_suffix.insert(0, '}')
            all_prefix = ''.join(cmd_prefix)
            all_suffix = ''.join(cmd_suffix)

            content = all_prefix + self._escape_latex(stylized_d['data']) + all_suffix
            #content = '{%s}' % content
            ret = self._surround_with_listing_escape(content)

        return ret



class HTML2LaTeXParser(HTMLParser):

    keyword_lst = ['font-weight', 'color', 'background-color', 'text-decoration-style']

    def __init__(self):
        super().__init__()
        self.latexifier = None
        self.style_stack = []
        self.pre_found = False

    def initialize_latexifier(self, **kwargs):
        self.latexifier = LaTeXify(**kwargs)

    # generate style dict based on current stack
    def generate_style_dict(self):
        result = dict()
        for lst in self.style_stack:
            for key, val in lst:
                result[key] = val
        return result

    def attrs_to_dict(self, attrs):
        ret = dict()
        for key, val in attrs:
            ret[key] = val
        return ret

    def parse_css_style(self, css_str):
        styles = css_str.split(';')
        result = dict()
        for style in styles:
            if len(style) == 0:
                continue

            key, val = style.split(':')
            key = key.strip()
            val = val.strip()
            assert len(key) > 0
            assert len(val) > 0
            result[key] = val

        return result

    def handle_starttag(self, tag, attrs):
        if not self.pre_found:
            if tag == 'pre':
                self.pre_found = True
            else:
                return

        attrs = self.attrs_to_dict(attrs)
        this_styles = []
        if tag == 'b':
            this_styles.append(('font-weight', 'bold'))
        elif tag == 'u':
            this_styles.append(('text-decoration-style', 'single'))
        elif tag == 'font':
            for kw in HTML2LaTeXParser.keyword_lst:
                if kw in attrs:
                    this_styles.append((kw, attrs[kw]))
        elif len(attrs) > 0:
            # dealing with some generic CSS
            if 'style' in attrs:
                css_styles = self.parse_css_style(attrs['style'])
                for kw in HTML2LaTeXParser.keyword_lst:
                    if kw in css_styles:
                        this_styles.append((kw, css_styles[kw]))

        self.style_stack.append(this_styles)

    def handle_endtag(self, tag):
        self.style_stack.pop()

    def handle_data(self, data):
        self.latexifier.set_style(self.generate_style_dict())
        self.latexifier.append_data(data)

    def get_lataxifier(self):
        return self.latexifier


def html_to_latex(html_str, **kwargs):
    parser = HTML2LaTeXParser()
    parser.initialize_latexifier(**kwargs)
    parser.feed(html_str)
    return parser.latexifier.dumps()


if __name__ == '__main__':

    class MyFrame(wx.Frame):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            sizer = wx.BoxSizer(wx.VERTICAL)
            self.panel = wx.Panel(self)

            self.SetSize(wx.Size(800, 600))
            self.SetTitle('HTML2LaTeX')

            self.textIn = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE)
            self.textOut = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
            sizer.Add(self.textIn, 1, wx.ALL | wx.EXPAND, 10)
            sizer.Add(self.textOut, 1, wx.ALL | wx.EXPAND, 10)

            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.chkXelatex = wx.CheckBox(self.panel, label='XeLaTeX')
            self.chkHex = wx.CheckBox(self.panel, label='Use Hex Char Code')
            self.btnConv = wx.Button(self.panel, label='Convert')
            self.btnConv.Bind(wx.EVT_BUTTON, self.evtBtn)
            hSizer.Add(self.chkXelatex, 0, wx.ALL | wx.ALIGN_CENTER, 10)
            hSizer.Add(self.chkHex, 0, wx.ALL | wx.ALIGN_CENTER, 10)
            hSizer.Add(self.btnConv, 1, wx.ALL | wx.ALIGN_CENTER, 10)

            sizer.Add(hSizer, 0, wx.ALL | wx.EXPAND)

            self.panel.SetSizerAndFit(sizer)

            self.Show()

        def evtBtn(self, evt):
            inText = self.textIn.GetValue()
            result = None
            try:
                result = html_to_latex(inText, escape_unicode=not self.chkXelatex.GetValue(),
                                       unicode_escape_mode='hex' if self.chkHex.GetValue() else 'dec')
            except Exception as e:
                wx.MessageBox('An exception occured during conversion: {}'.format(repr(e)), 'Exception', wx.OK | wx.ICON_ERROR)

            if result is not None:
                self.textOut.SetValue(result)


    app = wx.App()
    MyFrame(None)
    app.MainLoop()