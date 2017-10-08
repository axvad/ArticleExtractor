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

    __DEBUG = False

    def __init__(self):
        self.text = ""
        self.node = NodeHTML()

    def set_filter_rules(self, rules):

        self.rules = rules

    def get_as_clear_text(self, htmlText, includeKeys=None, excludeKeys=None):
        """return parsing text"""

        if (not includeKeys and not excludeKeys and len(self.rules)==0):
            return "Can't resolve. Need some filter key"

        res_text = ""

        for rule in self.rules:

            res_text += '\n'

            node = self.__parse(htmlText,rule.includeKeys,rule.excludeKeys)

            if not node:
                return None

            if PageTree.__DEBUG:
                node.pretty_print(True)

            hot_text = node.get_text()

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

        if PageTree.__DEBUG:
            self.node.pretty_print(True)

        inner_node = self.node

        if len(includeKeys)>1:
            for key in includeKeys[1:]:
                res = inner_node.find_node(key)

                if not res:
                    print("Can't find subkey \"{}\" in teg {}".format(key, inner_node.get_text()))
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

        patt = re.compile('<.*?>')

        result = patt.sub('', string)

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

    __DEBUG=False
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


        if NodeHTML.__DEBUG:
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

        if NodeHTML.__DEBUG:

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


class Rule:
    """save filter for site"""

    def __init__(self, name, priority, incudeKeys, excludeKeys=None, hostWords=None):
        self.name = name
        self.priority = priority
        self.includeKeys = incudeKeys if not incudeKeys or type(incudeKeys) is list else [incudeKeys]
        self.excludeKeys = excludeKeys if not excludeKeys or type(excludeKeys) is list  else [excludeKeys]
        self.hostWords = hostWords if not hostWords or type(hostWords) is list else [hostWords]


class HtmlToText:
    def __init__(self):
        self.__loader = PageLoader()
        self.__page = PageTree()
        self.__filter = ContextFilter()
        self.__file_save_origin_html = None #"recived_article.html"


    def load_settings(self, filename=None):

        if not filename:
            self.__filter.add_rule("default", Rule("default", 1, ["<body", "articlle"], ["AdCentre", "Adcent", "header"], ["&[a-zA-Z0-9]+;"]))

            self.__filter.add_rule("lenta.ru", Rule("Content", 2, ["b-topic__content"], ["<aside"], ["&[a-zA-Z0-9]+;"]))
            self.__filter.add_rule("gazeta.ru", Rule("Content", 2, ["<main", "article"], ["AdCentre", "id=\"Adcenter_Vertical\"", "id=\"right\"", "id=\"article_pants\""], ["&[a-zA-Z0-9]+;"])) #article_context article-text "main_article" "id=\"news-content\""
            self.__filter.add_rule("rambler.ru", Rule("Content", 2, ["class=\"article__center\""], None, ["&[a-zA-Z0-9]+;", '&nbsp'])) #"<body data", "<div class=\"page\"",
            self.__filter.add_rule("rt.com", Rule("Content", 1, ["class=\"article article_article-page\""], ["id=\"twitter", "blockquote class=\"twitter"], ["&[a-zA-Z0-9]+;"]))
            self.__filter.add_rule("vz.ru", Rule("Title", 1, ["class=\"fixed_wrap2\"", "<h1"], ["<table"], ["&[a-zA-Z0-9]+;"]))
            self.__filter.add_rule("vz.ru", Rule("Text", 2, ["class=\"text newtext\""], None, ["&[a-zA-Z0-9]+;"]))

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

        #test write full page as is
        if self.__file_save_origin_html:
            org_html = open(self.__file_save_origin_html, "w")
            org_html.write(intext)
            org_html.close()

        #load rules for page (True - for default rules)
        rules = self.__filter.get_rules(url, True)

        if rules:

            self.__page.set_filter_rules(rules)

            #intext = clearSpec(intext)

            text = self.__page.get_as_clear_text(intext)

            if text and len(text)>1:

                print("Parse article ({} charsets) from '{}'".format(len(text), url))

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

        return


def main():

    cito = ContextFilter()
    cito.add_rule("lenta.ru", Rule("Content", 2, ["b-topic__content"], ["<aside"], ["&[a-zA-Z0-9]+;"]))
    cito.add_rule("gazeta.ru", Rule("Content", 2, ["<main", "article"], ["AdCentre", "id=\"Adcenter_Vertical\"", "id=\"right\"", "id=\"article_pants\""], ["&[a-zA-Z0-9]+;"])) #article_context article-text "main_article" "id=\"news-content\""
    cito.add_rule("rambler.ru", Rule("Content", 2, ["class=\"article__center\""], None, ["&[a-zA-Z0-9]+;", '&nbsp'])) #"<body data", "<div class=\"page\"",
    cito.add_rule("rt.com", Rule("Content", 1, ["class=\"article article_article-page\""], ["id=\"twitter", "blockquote class=\"twitter"], ["&[a-zA-Z0-9]+;"]))
    cito.add_rule("yandex.ru", Rule("Annotation", 1, ["<body", "story__annot"], None, None))

    cito.add_rule("vz.ru", Rule("Title", 1, ["class=\"fixed_wrap2\"", "<h1"], ["<table"], ["&[a-zA-Z0-9]+;"]))
    cito.add_rule("vz.ru", Rule("Text", 2, ["class=\"text newtext\""], None, ["&[a-zA-Z0-9]+;"]))

    cito.add_rule("default", Rule("default", 1, ["<body", "articlle"], ["AdCentre", "Adcent", "header"], ["&[a-zA-Z0-9]+;"]))


    #LENTA.RU
    link = "https://lenta.ru/articles/2017/10/06/hypersonic/"
    link = "https://lenta.ru/news/2017/10/06/usaisisdruzba/"
    link = "https://lenta.ru/news/2017/10/06/triumf_saudi_dogovor/"
    link = "https://lenta.ru/news/2017/10/04/catalan/"
    link = "https://lenta.ru/news/2017/10/05/wane/"
    link = "https://lenta.ru/articles/2017/10/06/bognefraer/"

    #GAZETA.RU
    link = "https://www.gazeta.ru/science/2017/10/05_a_10917854.shtml"
    link = "https://www.gazeta.ru/army/news/10657904.shtml"
    link = "https://www.gazeta.ru/business/2017/10/06/10920080.shtml"
    link = "https://www.gazeta.ru/politics/2017/10/06_a_10919630.shtml"
    link = "https://www.gazeta.ru/army/2017/10/06/10919912.shtml"
    link = "https://www.gazeta.ru/tech/2017/08/17/10835450/mts_6minutes.shtml"
    link = "https://www.gazeta.ru/tech/2017/10/06/10920086/nsa_screwsup_again.shtml"

    # RAMBLER.RU
    link = "https://news.rambler.ru/politics/38002306-kak-tramp-naputstvoval-novogo-posla-ssha-v-rf/"
    link = "https://news.rambler.ru/army/38093890-pentagon-usomnilsya-v-sposobnosti-vks-pobedit-ig/?24smi=1"

    #RT.COM
    link = "https://russian.rt.com/sport/article/437268-chm-2018-otbor-kvalifikaciya?utm_medium=more&utm_source=rnews"
    link = "https://russian.rt.com/russia/news/437330-lukashenko-pozdravil-putin"
    link = "https://russian.rt.com/nopolitics/article/437214-film-salyut-7"

    # VZ.RU
    link = "https://vz.ru/news/2017/10/7/890029.html?utm_medium=more&utm_source=rnews"
    link = "https://vz.ru/news/2017/10/7/890025.html"

    # YANDEX.RU
    link = "https://news.yandex.ru/yandsearch?cl4url=iz.ru/655514/2017-10-07/polevye-komandiry-i-glavar-ig-ash-shishani-unichtozheny-vks-rf-v-sirii&lang=ru&from=main_portal&stid=ZJGYEcA3cvDOEQwxZfhg&lr=121608&msid=1507362660.04075.22877.19734&mlid=1507362372.glob_225.f020111a"

    #default filter
    link = "https://www.passion.ru/style/modnye-tendencii/kak-podgotovit-rebenka-k-kholodam-5-stilnykh-idei-dlya-vsekh-vozrastov.htm?utm_source=editorial&utm_medium=editorial&utm_campaign=Gulliver&utm_source=editorial&utm_medium=editorial&utm_campaign=gulliver"
    link = "http://24-rus.info/showbiz/aleksandr-maslyakov-skonchalsya/full/"
    link = "http://24-rus.info/politics/putin-razygral-velikolepnuyu-partiyu-postaviv-na-mesto-ukrainu-i-polshu/full/"
    link = "https://tmb.news/news/russia/15439_v_rossii_poyavitsya_novyy_perspektivnyy_avianosets/?utm_source=24smi&utm_medium=referral&utm_term=1302&utm_content=1318549&utm_campaign=10923"

    # redirect
    link = "https://palacesquare.rambler.ru/sqgelhtx/MThvcms1LjRlNGpAeyJkYXRhIjp7IkFjdGlvbiI6IlJlZGlyZWN0IiwiUmVmZmVyZXIiOiJodHRwczovL2xlbnRhLnJ1L3J1YnJpY3MvcnVzc2lhLyIsIlByb3RvY29sIjoiaHR0cHM6IiwiSG9zdCI6ImxlbnRhLnJ1In0sImxpbmsiOiJodHRwczovL2FuLnlhbmRleC5ydS9tYXB1aWQvbGVudGFydS8wNjg3ZjdjMzVjYjgwNzQzYjhiNmJkM2JkOWFiNTVmMD9qc3JlZGlyPTEmbG9jYXRpb249aHR0cHMlM0ElMkYlMkZsZW50YS5ydSUyRmFydGljbGVzJTJGMjAxNyUyRjEwJTJGMDYlMkZib2duZWZyYWVyJTJGIn0%3D"

    link = "https://vz.ru/news/2017/10/6/889991.html"

    filename = "/home/sam/Programming/Git/SiteTextExtractor/export_test.html"

    # here will be load setting
    setting = open("site_export_settings.ini","w")

    setting.write(str(cito))

    setting.close()

    # load page
    loader = PageLoader()

    f = loader.getHtmlPage(link)

    if f.status_code == 200:

        page = PageTree()

        intext = f.text

        #test write full page as is
        fl = open(filename, "w")
        fl.write(intext)
        fl.close()

        #load rules for page
        rules = cito.get_rules(link, True)

        if rules:

            page.set_filter_rules(rules)

            #intext = clearSpec(intext)

            text = page.get_as_clear_text(intext)

            if text and len(text)>1:
                print('\n'+link)
                print(text)


    else:
        print('Bad response from site: code '+str(f.status_code))

def run_extractor(link,outputfilename):

    #link = "https://lenta.ru/news/2017/10/06/triumf_saudi_dogovor/"

    html  = HtmlToText()

    html.load_settings()

    html.get_text_article(link,outputfilename)


def load_settings():
    pass

def print_help():
    helping = "\n\
    Программа сохраняет адресный текст страницы (без рекламы) в txt файл директории ./result/url.txt\n\n\
    Формат запуcка: article2text.exe \"url_1\" \"url_2\" ...\n\
        url - ссылки на статьи в формате \"http://some.ru/mega_nuews\"\n\
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

    for ar in sys.argv[1:]:
        out_file = outputfilename(ar)
        if len(out_file)>2:
            print("Extracting {} to {}".format(ar, out_file))
            run_extractor(ar, out_file)
        else:
            print("Can't response link: {}".format(ar))


