import sys
import os
import requests
import re


class PageLoader:
    '''class load html page'''
    url=""

    def __init__(self):
        self.url = ""

    def getHtmlPage(self, url):
        return requests.get(url)


class PageTree:
    """Class parsing html page as tree of nodes"""

    DEBUG = False

    def __init__(self):
        self.text = ""
        self.node = NodeHTML()

    def set_filter_rules(self, rules):

        self.rules = rules

    def get_as_clear_text(self, htmlText):
        """return parsing text"""

        if (len(self.rules)==0):
            return "Can't resolve. Need some filter key"

        res_text = ""

        for rule in self.rules:

            res_text += '\n'

            node = self.__parse(htmlText,rule.includeKeys,rule.excludeKeys)

            if not node:
                return None

            if NodeHTML.DEBUG:
                node.pretty_print(NodeHTML.DEBUG)

            hot_text = node.get_text()

            if PageTree.DEBUG:
                print('Nodes text: '+hot_text)
            # extract text from <p> and <h..> teg
            text = re.findall('<[ph][^>]*>(.*?)</[ph][0-9]*>',hot_text)

            for line in text:
                fab = self.__replaceHREF(line)
                fab = self.__clearTeg(fab)
                fab = self.__clearHostWords(fab, rule.hostWords)

                res_text = res_text + self.__line_width(fab) + '\n\n'

            #clear node for new search
            self.node= NodeHTML()

        return res_text

    def __parse(self, htmlText, includeKeys, excludeKeys):

        pos = htmlText.find(includeKeys[0])

        if pos <0:
            print("Can't find key [{}] in HTML({} symbols)".format(includeKeys[0],len(htmlText)))
            return None

        self.node.create(htmlText, pos)

        if NodeHTML.DEBUG:
            self.node.pretty_print(NodeHTML.DEBUG)

        inner_node = self.node

        if len(includeKeys)>1:
            for key in includeKeys[1:]:
                res = inner_node.find_node(key)

                if not res:
                    print("Warning: Can't find subkey \"{}\" in teg {}"\
                          .format(key, PageTree.clearSpec(inner_node.get_text()[:40])))
                    break

                else:
                    inner_node = res

        if excludeKeys and len(excludeKeys)>0:
            for exc in excludeKeys:
                inner_node.exclude_all(exc)

        return inner_node

    def __line_width(self, long_string, width = 80):
        """Set width for string, cut \n if longer"""

        litle_strings = long_string.split('\n')

        res = ""

        for s in litle_strings:

            if len(s)>width:
                lws = s.rfind(' ', 1, width)
                lws = width if lws<1 else lws
                res = res + s[:lws].rstrip()+'\n' + self.__line_width(s[lws:]).lstrip()

            else:
                res = res + s

        return res

    def __replaceHREF(self, string):
        patt = re.compile('<a href=[\"]?(.*?)[\" ].*?>(.*?)</a>')
        result = patt.sub('\g<2> [\g<1>]', string)
        return result

    def __clearTeg(self, string):
        """finally - clear all teg from text"""

        result = re.sub('<.*?>', '', string)
        result = re.sub('(&[a-zA-Z0-9#]+;)','', result)

        return result

    def __clearHostWords(self, string, hostWords):

        if not hostWords:
            return string

        result = string

        for word in hostWords:
            result = re.sub(word,'', result)

        return result

    def clearSpec(string):
        """clear all \n, \r, \t symbols"""
        return re.sub('[\n\r\t]+', '', string)


class NodeHTML:
    """Class for seve html page as tree nodes"""

    DEBUG=False
    __print_space=0

    def __init__(self):
        self.child_nodes = []
        self.head = ""
        self.start = 0
        self.end = 0
        self.text = ""
        self.parent = None
        self.blocked = False

    def __str__ (self):
        return "%s[s%d,e%d] with %d childs"%(self.head, self.start, self.end, len(self.child_nodes))

    def add_parent(self, parentNode):
        self.parent = parentNode

    def create(self,text, position):

        patt_open_teg = '<([a-z0-9]+)[\n >]'
        patt_close_teg = '/[a-z0-9]*>'
        onestring_teg = ["area", "base", "br", "col", "command", "embed", "hr", "img", "input", "keygen", "link", "meta", "param", "source", "track", "wbr"]

        self.text = text

        self.start = text[:position+1].rfind("<")

        find_open_teg = re.match(patt_open_teg,text[self.start:self.start+30])

        if not find_open_teg:
            print("Can't find open html teg at {} (pos:{})".format(PageTree.clearSpec(self.text[self.start:self.start+30]),position))
            return None

        self.head = find_open_teg.group(1)

        if self.head in onestring_teg:
            self.end = text[self.start:].find(">")+self.start+1
            return self.end

        if self.head == 'script':
            close_teg = '/script>'
            inner_teg = '<<0>>'
        else:
            close_teg = patt_close_teg #'/[a-z0-9]*>'
            inner_teg = patt_open_teg #'<[a-z0-9]+[ >]'


        if NodeHTML.DEBUG:
            desc = re.match('.*[^\n].*',text[self.start:self.start+80]).group()
            print ('{:.{align}{width}}{} [{:^6},{:^6}] {}'.format('', self.head, self.start, "????", desc, align='>', width=NodeHTML.__print_space))
            NodeHTML.__print_space += 2

        start_child = self.start+1
        end_child = start_child

        while True:

            find_close_teg = re.search(close_teg, text[end_child:])

            pos_close_teg = end_child+find_close_teg.start()+len(find_close_teg.group())

            inn = re.search(inner_teg, text[end_child:pos_close_teg])

            if inn:

                start_child = end_child+inn.start()

                child_node = NodeHTML()

                child_node.add_parent(self)

                end_child = child_node.create(text,start_child)

                self.child_nodes.append(child_node)

            else:

                self.end = pos_close_teg
                break

        if NodeHTML.DEBUG:

            NodeHTML.__print_space -= 2
            print ('{:.{align}{width}}{} [{:^6},{:^6}] Childs:{}'.format('', self.head, self.start, self.end, len(self.child_nodes), align='>', width=NodeHTML.__print_space))

        return pos_close_teg

    def find_node(self, key):
        '''return node with text like [key]'''

        pos = self.text.find(key,self.start,self.end)

        return self.get_node(pos)

    def find_all_nodes(self, keyString):

        posAll = re.finditer(keyString, self.text)

        result = []

        for i in posAll:
            fn = self.get_node(i.start())
            if fn:
                result.append(fn)

        return result

    def exclude_all (self, excludeKeyString):

        findednodes = self.find_all_nodes(excludeKeyString)

        for node in findednodes:
            node.blocked = True

        return self

    def get_node(self, position):

        min_end = self.end

        for child in self.child_nodes:
            if child.start < min_end:
                min_end = child.start

        if position >= self.start and position < min_end:
            return self

        else:
            for child in self.child_nodes:
                res = child.get_node(position)
                if res:
                    return res

        return None

    def pretty_print(self, isPrintBody):
        '''Print node pointer with childs as tree'''

        print('{:.{align}{width}}{} body[{}]'.format('', self, self.get_text() if isPrintBody else "", align='>', width=NodeHTML.__print_space))

        NodeHTML.__print_space +=2

        for inner in self.child_nodes:
            inner.pretty_print(isPrintBody)

        NodeHTML.__print_space -= 2

        print('{:.{align}{width}}{} end with[{}] need/{}'.format('', self, PageTree.clearSpec(self.text[self.end-50:self.end+10]), self.head, align='>', width=NodeHTML.__print_space))

    def get_text(self):

        if self.blocked:
            return ""

        result = ""

        ls_child = sorted(self.child_nodes,key=lambda t:t.start)

        if ls_child:
            min = self.end
            max = self.start

            cur_start = self.start

            for ls in ls_child:
                result = result + self.text[cur_start:ls.start] + ls.get_text()
                cur_start = ls.end

            result = result+self.text[cur_start:self.end]

        else:
            result = self.text[self.start:self.end]

        #result = PageTree.clearSpec(result)

        return result


class ContextFilter:
    """save and represent filters fo sites"""

    def __init__(self):
        self.__filters = {}

    def add_rule(self, host, rule):
        if host in self.__filters:
            self.__filters[host].append(rule)
        else:
            self.__filters[host]=[rule]

    def get_rules(self, url, getDefaultRule = True):

        rules = []

        host = self.get_host(url)

        if host not in self.__filters and getDefaultRule:
            host = "default"

        rules = sorted(self.__filters[host], key=lambda t:t.priority)

        return rules

    def get_host(self, url):

        patt = re.compile('(http://)?([\w-]+\.)?(?P<host>[\w-]+)\.(?P<domen>\w+)/.+')

        match_host = patt.search(url)

        host = ""

        if match_host:
            host = match_host.group('host')+'.'+match_host.group('domen')
        else:
            print("Can't find host (like 'rambler.ru') in link {}.".format(url))
            return None #"Can't resolve host from url: "+url

        return host

    def load_from_file(self, filename):

        fs = open(filename, 'r')

        num_line = 0
        start_filter = False
        patt = re.compile('^([^:]+):? ({[^{^}]})+ ')

        for line in fs:
            num_line += 1
            if start_filter:
                host = re.match(r'^([^:]+):',line)

                if not host:
                    print("Can't response settings: 'host' at line {}".format(num_line))
                    continue

                rules = re.findall(' ({[^{^}]+})',line)

                if not rules or len(rules) == 0:
                    print("Can't response rules for {} at line {}".format(host.group(1), num_line))
                    continue

                for rl in rules:
                    rule = Rule.parse(rl)

                    if host.group(1) in self.__filters.keys():
                        self.__filters[host.group(1)].append(rule)
                    else:
                        self.__filters[host.group(1)] = [rule]

            elif line.startswith('FILTERS:'):
                start_filter = True

    def save_to_file(self,filename):

        fs = open(filename, 'w')

        title = "# Настройки фильтров для некоторых новостных сайтов.\n\
        # Структура фильтра:\n\
        # <HOST.COM>: {<Name>; <Priority>; ['<includeKey1>','<includeKey2>']; \n\
        #			['<excludeKey1>','<excludeKey2>']; ['hostword1']; }\n\
        #\n\
        # Для одного host может быть определено несколько фильтров, обрабатываемых в \n\
        # порядке ключа приоритета для возможности комбинировать данные из нескольких \n\
        # блоков HTML (например заголовок и текст могут определятся отдельно)\n\
        #\n\
        # Настройки считываются после строки, начинающейся с FILTERS\n"

        fs.write(title)

        fs.write('\nFILTERS:\n')

        for flt in self.__filters.keys():
            fs.write('{}:'.format(flt))
            for rule in self.__filters[flt]:
                fs.write(' {'+str(rule)+'}')

            fs.write('\n')

        fs.close()


class Rule:
    """ Tune rules for site
        name - идентификатор правила
        priority - порядок применения rules
        includeKeys - вложенные уровни поиска блока html
        excludeKey - исключение блоков html, содержащих ключевые слова
        hostWords - отчистка текста от служебных слов хоста
    """

    def __init__(self, name, priority, incudeKeys, excludeKeys=None, hostWords=None):
        self.name = name
        self.priority = priority
        self.includeKeys = incudeKeys if not incudeKeys or type(incudeKeys) is list else [incudeKeys]
        self.excludeKeys = excludeKeys if not excludeKeys or type(excludeKeys) is list  else [excludeKeys]
        self.hostWords = hostWords if not hostWords or type(hostWords) is list else [hostWords]

    def __str__(self):
        result = '{}; {}; {}; {}; {}; '.format(
            self.name,
            self.priority,
            self.includeKeys,
            self.excludeKeys,
            self.hostWords)

        return result

    def parse(string):
        m = re.findall(r'[{ ]([^;]+);', string)

        inc = re.findall('\'([^\']+)\'', m[2])
        exc = re.findall('\'([^\']+)\'', m[3])
        wrd = re.findall('\'([^\']+)\'', m[4])

        rule = Rule(m[0], m[1], inc, exc, wrd)
        if HtmlToText.DEBUG:
            print(rule)

        return rule


class HtmlToText:
    """ Main class for parsing sites """

    DEBUG = False

    SAVE_HTML = False

    def __init__(self):
        self.__loader = PageLoader()
        self.__page = PageTree()
        self.__filter = ContextFilter()
        self.__file_save_origin_html = None


    def load_settings(self, filename=None):

        filename = os.curdir+'/filter.ini'

        try:
            os.stat(filename)

            self.__filter.load_from_file(filename)

        except FileNotFoundError:

            self.__filter.add_rule("default", Rule("default", 1, ["<body", "articlle"], ["AdCentre", "Adcent", "header"], None))

            self.__filter.add_rule("lenta.ru", Rule("Content", 2, ["b-topic__content"], ["<aside"], None))
            self.__filter.add_rule("gazeta.ru", Rule("Content", 2, ["<main", "article"], ["AdCentre", "id=\"Adcenter_Vertical\"", "id=\"right\"", "id=\"article_pants\""], None)) #article_context article-text "main_article" "id=\"news-content\""
            self.__filter.add_rule("rambler.ru", Rule("Content", 2, ["class=\"article__center\""], None, None)) #"<body data", "<div class=\"page\"",
            self.__filter.add_rule("rt.com", Rule("Content", 1, ["class=\"article article_article-page\""], ["id=\"twitter", "blockquote class=\"twitter"], None))
            self.__filter.add_rule("vz.ru", Rule("Title", 1, ["class=\"fixed_wrap2\"", "<h1"], ["<table"], None))
            self.__filter.add_rule("vz.ru", Rule("Text", 2, ["class=\"text newtext\""], None, None))

            self.__filter.save_to_file(filename)

    def get_filename_from_url(self, url):
        #result = re.sub(r'^http://([^\/]+)?/.*$','\1',url)
        return "article_result.txt"

    def get_text_article(self, url, out_filename = None):

        # load page
        html_page = self.__loader.getHtmlPage(url)

        if html_page.status_code != 200:
            print('Bad response from site: code '+str(html_page.status_code))
            return

        intext = html_page.text

        print("HTML page loaded. {} charsets".format(len(intext)))

        if HtmlToText.SAVE_HTML:
            html_file = out_filename.replace('.txt', '.html')
            hf = open(html_file,"w")
            hf.write(intext)
            hf.close()

        #load rules for page (True - for default rules)
        rules = self.__filter.get_rules(url, True)

        if rules:

            self.__page.set_filter_rules(rules)

            #intext = clearSpec(intext)

            text = self.__page.get_as_clear_text(intext)

            if text and len(text)>1:

                print("Parse article ({} charsets) from '{}'".format(len(text), url))

                if HtmlToText.DEBUG:
                    print('\n'+url)
                    print(text)

                if not out_filename:
                    out_filename = self.get_filename_from_url(url)

                res_file = open(out_filename,"w")

                res_file.write(text)

                res_file.close()

                print("Result saved in {}".format(out_filename))

            else:
                print("Can't parse article. Nothing for save.")

        print('\n')
        return


def run_extractor(link,outputfilename, isLogged='nothing'):

    if re.search('main', isLogged):
        HtmlToText.DEBUG = True

    if re.search('page', isLogged):
        PageTree.DEBUG = True

    if re.search('node', isLogged):
        NodeHTML.DEBUG = True

    html = HtmlToText()

    html.load_settings()

    print("Settings loaded")

    html.get_text_article(link,outputfilename)


def print_help():
    helping = "\n\
    Программа сохраняет адресный текст страницы (без рекламы) в txt файл директории ./result/url.txt\n\n\
    Формат запуcка: article2text.exe [+html] [+d:main +d:page] \"url_1\" \"url_2\" ...\n\
        url - ссылки на статьи в формате \"http://some.ru/mega_nuews\"\n\
        +html - сохраняет загруженный текст страницы ./result/url.html\n\
        +d: - вывод лога работы (+d:main - верхний уровеньб +d:page - parsing страницы)\n\
    \n\
    Настройки фильтров дополнять в файле filter.ini\n\n"

    print(helping)


def outputfilename(url):
    r = re.search(r'(https?://)?([\da-z.-]+)\.([a-z.]{2,6})([/\d\w .-]*)', url)

    if not r:
        return ""

    out_dir = os.curdir + '/' + "/result/"\
              +(r.group(2)+r.group(3)).replace(".", '')

    file_name = r.group(4).replace("/", "_")

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    i=0
    while True:
        filename = out_dir+"/"+file_name + '({}).txt'.format(i)
        try:
            os.stat(filename)
            i += 1

        except FileNotFoundError:
            break

        if i > 20:
            print("Too match files in " + filename)
            break

    return filename


if __name__ == '__main__':

    if len (sys.argv) == 1:
        print_help()
        sys.exit()

    debug = ""
    for ar in sys.argv[1:]:
        #save recived html page in .\result\url.html
        if re.search('\+html', ar):
            HtmlToText.SAVE_HTML = True
            continue

        #log top level info
        if re.search("\+d:main",ar):
            debug += ' main'
            continue

        #log parse page
        if re.search("\+d:page",ar):
            debug += ' page'
            continue

        #create file name from url (and check valid url)
        out_file = outputfilename(ar)

        if len(out_file)>12:
            print("\nStart for {}".format(ar, out_file))
            run_extractor(ar, out_file, debug)
        else:
            print("Can't response link: {}".format(ar))


