from html.parser import HTMLParser
from colour import Color
from pylatex.utils import escape_latex, NoEscape
import re
import wx


def get_default_entity():
    return {
        'tag': None,
        'data': [],
        'attrs': None,
        'last_pointer': None
    }


class AhaHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.root = get_default_entity()
        self.root['tag'] = '@root'
        self.treeStorage = [self.root]

        self.curPointer = self.root

    def handle_starttag(self, tag, attrs):
        # create new structure in the tree
        entity = get_default_entity()
        entity['last_pointer'] = self.curPointer
        entity['tag'] = tag
        entity['attrs'] = attrs
        self.treeStorage.append(entity)
        self.curPointer = entity

    def handle_endtag(self, tag):
        # append this entity to last pointer
        self.curPointer['last_pointer']['data'].append(self.curPointer)
        self.curPointer = self.curPointer['last_pointer']

    def handle_data(self, data):
        # append data to current pointer
        dataEntity = get_default_entity()
        dataEntity['data'].append(data)
        self.curPointer['data'].append(dataEntity)


def get_html_tree_f(filename):
    with open(filename, 'r') as infile:
        htmlContent = infile.read()
    parser = AhaHTMLParser()
    parser.feed(htmlContent)
    return (parser.root, parser.treeStorage)

def get_html_tree(text):
    parser = AhaHTMLParser()
    parser.feed(text)
    return (parser.root, parser.treeStorage)

def find_pre_in_tree(node):
    if node['tag'] == 'pre':
        return node

    for data in node['data']:
        if isinstance(data, dict):
            result = find_pre_in_tree(data)
            if result is not None:
                return result

    return None


def parse_css_style(styleStr):
    styles = styleStr.split(';')
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


class HTMLTree2Latex:

    def __init__(self):
        self.colorConv = dict()
        self.result = []

        self.colorNameConvDict = dict()
        for i in range(ord('A'), ord('F') + 1):
            self.colorNameConvDict[chr(i)] = chr(i)
        for i in range(ord('0'), ord('9') + 1):
            self.colorNameConvDict[chr(i)] = chr(ord('F') + 1 + i - ord('0'))


    def to_latex(self, node):
        self.result.clear()
        self.colorConv.clear()

        self._to_latex(node)
        # generate color definition
        colorDefFormat = r'\definecolor{%s}{HTML}{%s}'

        colorDefs = []
        for key, val in self.colorConv.items():
            colorDef = colorDefFormat % (val['latex_name'], val['value'])
            colorDefs.append(NoEscape(colorDef))

        colorDefStr = '\n'.join(colorDefs)

        return colorDefStr, self.result

    def _get_color_item(self, colorStr):
        if colorStr[0] == '#':
            assert len(colorStr) == 7
            capStr = colorStr[1:].upper()
            capStr = ''.join([self.colorNameConvDict[x] for x in capStr])

            if capStr not in self.colorConv:
                colorItem = dict()
                colorItem['latex_name'] = self._get_color_latex_name(capStr)
                colorItem['value'] = colorStr[1:]
                self.colorConv[capStr] = colorItem

            colorStr = capStr

        if colorStr not in self.colorConv:
            # create new color item
            colorItem = dict()
            colorItem['latex_name'] = self._get_color_latex_name(colorStr)
            colorItem['value'] = Color(colorStr).get_hex_l()[1:]
            self.colorConv[colorStr] = colorItem

        colorItem = self.colorConv[colorStr]
        return colorItem

    def _get_color_latex_name(self, color):
        return 'xxxhtmlcolor{}'.format(color)

    def _escape_utf8(self, data):
        reconData = []
        for s in data:
            if ord(s) < 128:
                reconData.append(s)
            else:
            	sInd = ord(s)
            	if sInd == 0xfffd:
            		reconData.append('%*\\ucr*)')
            	elif sInd == 0x2588:
            		reconData.append(r'%*$\blacksquare$*)')
            	else:
	                hexCode = '{:x}'.format(ord(s))
	                escapedS = '%*\\unichar{{\"{}}}*)'.format(hexCode)
	                reconData.append(escapedS)
        return NoEscape(''.join(reconData))

    # allow consecutive white spaces in latex
    def _escape_whitespace(self, data):
        reconData = []
        for s in data:
            if s == ' ':
                reconData.append(NoEscape(r'\space '))
            else:
                reconData.append(s)
        return reconData

    def _to_latex(self, node, inLatex = False):
        result = self.result

        # process style
        hasLatex = False
        endCap = []

        startResultSize = len(result)

        # dealing with specific tags
        if node['tag'] == 'b':
            hasLatex = True
            result.append(NoEscape(r'{\bfseries '))
            endCap.insert(0, NoEscape('}'))
        elif node['tag'] == 'font':
            # dealing with font color
            for key, val in node['attrs']:
                if key == 'color':
                    hasLatex = True
                    colorStr = val
                    colorItem = self._get_color_item(colorStr)
                    result.append(NoEscape(r'{\color{%s}' % colorItem['latex_name']))
                    endCap.insert(0, NoEscape('}'))
        else:
            # dealing with generic tags with css styles
            if node['attrs'] is not None:
                for key, val in node['attrs']:
                    if key == 'style':
                        # if there is style, then the entity has to be escaped
                        hasLatex = True
                        cssStyle = parse_css_style(val)

                        if 'font-weight' in cssStyle:
                            if cssStyle['font-weight'] == 'bold':
                                result.append(NoEscape(r'{\bfseries '))
                                endCap.insert(0, NoEscape('}'))

                        if 'color' in cssStyle:
                            colorStr = cssStyle['color']
                            colorItem = self._get_color_item(colorStr)
                            result.append(NoEscape(r'{\color{%s}' % colorItem['latex_name']))
                            endCap.insert(0, NoEscape('}'))

                        if 'background-color' in cssStyle:
                            self.addColorBoxDef = True
                            colorStr = cssStyle['background-color']
                            colorItem = self._get_color_item(colorStr)
                            result.append(NoEscape(r'\smash{\colorbox{%s}{'%colorItem['latex_name']))
                            endCap.insert(0, NoEscape('}}'))

        if hasLatex:
            if not inLatex:
                result.insert(startResultSize, '%*')
                endCap.append('*)')
                inLatex = True

        startResultSize = len(result)

        for data in node['data']:
            if isinstance(data, str):
                if inLatex:
                    # if in escape mode, just put in UTF-8 characters
                    result.extend(self._escape_whitespace(data))
                else:
                    result.append(self._escape_utf8(data))

            elif isinstance(data, dict):
                self._to_latex(data, inLatex)

        if hasLatex:
            for i in range(startResultSize, len(result)):
                if not isinstance(result[i], NoEscape):
                    # preserve NoEscape
                    result[i] = escape_latex(result[i])
            result.extend(endCap)


def html_to_console_style_f(filename):
    root, tree = get_html_tree_f(filename)
    preEntity = find_pre_in_tree(root)
    assert preEntity is not None
    html2altex = HTMLTree2Latex()
    colorDef, content = html2altex.to_latex(preEntity)

    outputFmt = r'''{\lstconsolestylenf
%s
\begin{consolebox}
\begin{lstlisting}
%s
\end{lstlisting}
\end{consolebox}}'''

    return outputFmt%(colorDef, ''.join(content))

def html_to_console_style(text):
    root, tree = get_html_tree(text)
    preEntity = find_pre_in_tree(root)
    assert preEntity is not None
    html2altex = HTMLTree2Latex()
    colorDef, content = html2altex.to_latex(preEntity)

    outputFmt = r'''{
%s
\setlength{\fboxsep}{0pt}
\begin{tcbconsole}
%s
\end{tcbconsole}
}'''
    
    result = outputFmt % (colorDef, ''.join(content).strip())
    return result.encode('utf8')

if __name__ == '__main__':
    # run the GUI

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

            self.btnConv = wx.Button(self.panel, label='Convert')
            self.btnConv.Bind(wx.EVT_BUTTON, self.evtBtn)
            sizer.Add(self.btnConv, 0, wx.ALL | wx.ALIGN_CENTER, 5)

            self.panel.SetSizerAndFit(sizer)

            self.Show()

        def evtBtn(self, evt):
            inText = self.textIn.GetValue()
            result = None
            try:
                result = html_to_console_style(inText)
            except Exception as e:
                wx.MessageBox('An exception occured during conversion: {}'.format(repr(e)), 'Exception', wx.OK | wx.ICON_ERROR)

            if result is not None:
                self.textOut.SetValue(result)


    app = wx.App()
    MyFrame(None)
    app.MainLoop()
