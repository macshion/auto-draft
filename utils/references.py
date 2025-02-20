# Each `paper` is a dictionary containing:
#       (1) paper_id (2) title (3) authors (4) year (5) link (6) abstract (7) journal (8) embeddings
#
# Generate references:
#   `Reference` class:
#       1. Read a given .bib file to collect papers; use `search_paper_abstract` method to fill missing abstract.
#       2. Given some keywords; use Semantic Scholar API to find papers.
#       3. Generate bibtex from the selected papers. --> to_bibtex()
#       4. Generate prompts from the selected papers: --> to_prompts()
#               A sample prompt: {"paper_id": "paper summary"}

# todo: (1) citations & citedby of provided papers:
    #       load the pre-defined papers; use S2 to find all related works
    #       add all citations to `bib_papers`
    #       add all citedby to `bib_papers`
    #       use Semantic Scholar to find their embeddings
#       (2) separate references:
    #       divide references into different groups to reduce the tokens count
    #       for generating different paragraph of related works, use different set of references

import requests
import re
import bibtexparser
import random
from scholarly import scholarly
from scholarly import ProxyGenerator


######################################################################################################################
# Some basic tools
######################################################################################################################
def remove_newlines(serie):
    # This function is applied to the abstract of each paper to reduce the length of prompts.
    serie = serie.replace('\n', ' ')
    serie = serie.replace('\\n', ' ')
    serie = serie.replace('  ', ' ')
    serie = serie.replace('  ', ' ')
    return serie


def search_paper_abstract(title):
    pg = ProxyGenerator()
    success = pg.FreeProxies() #pg.ScraperAPI("921b16f94d701308b9d9b4456ddde155")
    if success:
        try:
            scholarly.use_proxy(pg)
            # input the title of a paper, return its abstract
            search_query = scholarly.search_pubs(title)
            found_paper = next(search_query)
        except:
            return ""
    else:
        return ""
        # raise RuntimeError("ScraperAPI fails.")
    return remove_newlines(found_paper['bib']['abstract'])


def load_papers_from_bibtex(bib_file_path):
    with open(bib_file_path) as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)
    if len(bib_database.entries) == 0:
        return []
    else:
        bib_papers = []
        for bibitem in bib_database.entries:
            # Add each paper to `bib_papers`
            paper_id = bibitem.get("ID")
            title = bibitem.get("title")
            if title is None:
                continue
            journal = bibitem.get("journal")
            year = bibitem.get("year")
            author = bibitem.get("author")
            abstract = bibitem.get("abstract")
            if abstract is None:
                abstract = search_paper_abstract(title)
            result = {
                "paper_id": paper_id,
                "title": title,
                "link": "",
                "abstract": abstract,
                "authors": author,
                "year": year,
                "journal": journal
            }
            bib_papers.append(result)
        return bib_papers

######################################################################################################################
# Semantic Scholar (SS) API
######################################################################################################################
def ss_search(keywords, limit=20, fields=None):
    # space between the  query to be removed and replaced with +
    if fields is None:
        fields = ["title", "abstract", "venue", "year", "authors", "tldr", "embedding", "externalIds"]
    keywords = keywords.lower()
    keywords = keywords.replace(" ", "+")
    url = f'https://api.semanticscholar.org/graph/v1/paper/search?query={keywords}&limit={limit}&fields={",".join(fields)}'
    # headers = {"Accept": "*/*", "x-api-key": constants.S2_KEY}
    headers = {"Accept": "*/*"}

    response = requests.get(url, headers=headers, timeout=30)
    return response.json()


def _collect_papers_ss(keyword, counts=3, tldr=False):
    def externalIds2link(externalIds):
        # Sample externalIds:
        #   "{'MAG': '2932819148', 'DBLP': 'conf/icml/HaarnojaZAL18', 'ArXiv': '1801.01290', 'CorpusId': 28202810}"
        if externalIds:
            # Supports ArXiv, MAG, ACL, PubMed, Medline, PubMedCentral, DBLP, DOI
            # priority: DBLP > arXiv > (todo: MAG > CorpusId > DOI > ACL > PubMed > Mdeline > PubMedCentral)
            # DBLP
            dblp_id = externalIds.get('DBLP')
            if dblp_id is not None:
                dblp_link = f"dblp.org/rec/{dblp_id}"
                return dblp_link
            # arXiv
            arxiv_id = externalIds.get('ArXiv')
            if arxiv_id is not None:
                arxiv_link = f"arxiv.org/abs/{arxiv_id}"
                return arxiv_link
            return ""
        else:
            # if this is an empty dictionary, return an empty string
            return ""

    def extract_paper_id(last_name, year_str, title):
        pattern = r'^\w+'
        words = re.findall(pattern, title)
        # return last_name + year_str + title.split(' ', 1)[0]
        try:
            output = last_name + year_str + words[0]
        except IndexError:
            output = last_name + year_str + title[:4]
        return output

    def extract_author_info(raw_authors):
        authors = [author['name'] for author in raw_authors]

        authors_str = " and ".join(authors)
        try:
            last_name = authors[0].split()[-1]
            last_name = last_name.replace("'", "")
        except IndexError:
            last_name = "ma"
        # pattern = r'^\w+'
        # last_name = re.findall(pattern, authors[0])
        return authors_str, last_name

    def parse_search_results(search_results_ss):
        if len(search_results_ss) == 0:
            return []

        # turn the search result to a list of paper dictionary.
        papers_ss = []
        for raw_paper in search_results_ss:
            if raw_paper["abstract"] is None:
                continue

            authors_str, last_name = extract_author_info(raw_paper['authors'])
            year_str = str(raw_paper['year'])
            title = raw_paper['title']

            # some journal may contain &; replace it. e.g. journal={IEEE Power & Energy Society General Meeting}
            journal = raw_paper['venue'].replace("&", "\\&")
            if not journal:
                journal = "arXiv preprint"

            paper_id = extract_paper_id(last_name, year_str, title).lower()
            link = externalIds2link(raw_paper['externalIds'])

            if tldr and raw_paper['tldr'] is not None:
                abstract = raw_paper['tldr']['text']
            else:
                abstract = remove_newlines(raw_paper['abstract'])

            # some papers have no embeddings; handle this case
            embeddings_dict = raw_paper.get('embedding')
            if embeddings_dict is None:
                continue
            else:
                embeddings = raw_paper['embedding']['vector']
            result = {
                "paper_id": paper_id,
                "title": title,
                "abstract": abstract,
                "link": link,
                "authors": authors_str,
                "year": year_str,
                "journal": journal,
                "embeddings": embeddings
            }
            papers_ss.append(result)
        return papers_ss

    raw_results = ss_search(keyword, limit=counts)
    if raw_results is not None:
        search_results = raw_results.get("data")
        if search_results is None:
            search_results = []
    else:
        search_results = []
    results = parse_search_results(search_results)
    return results

######################################################################################################################
# References Class
######################################################################################################################

class References:
    def __init__(self, title, load_papers):
        if load_papers is not None:
            self.papers = {}
            self.papers["customized_refs"] = load_papers_from_bibtex(load_papers)
        else:
            self.papers = {}
        self.title = title

    def load_papers(self, bibtex, keyword):
        self.papers[keyword] = load_papers_from_bibtex(bibtex)

    def generate_keywords_dict(self):
        keywords_dict = {}
        for k in self.papers:
            keywords_dict[k] = len(self.papers[k])
        return keywords_dict

    def collect_papers(self, keywords_dict, tldr=False):
        """
        keywords_dict:
            {"machine learning": 5, "language model": 2};
            the first is the keyword, the second is how many references are needed.
        """
        for key, counts in keywords_dict.items():
            self.papers[key] = _collect_papers_ss(key, counts, tldr)


    def to_bibtex(self, path_to_bibtex="ref.bib", max_num_refs=50):
        """
        Turn the saved paper list into bibtex file "ref.bib". Return a list of all `paper_id`.
        """
        # todo:
        #   use embeddings to evaluate; keep top k relevant references in papers
        #   send (title, .bib file) to evaluate embeddings; recieve truncated papers
        papers = self._get_papers(keyword = "_all")
        random.shuffle(papers)
        papers = papers[:max_num_refs]

        # clear the bibtex file
        with open(path_to_bibtex, "w", encoding="utf-8") as file:
            file.write("")

        bibtex_entries = []
        paper_ids = []
        seen = set()
        for paper in papers:
            if paper["paper_id"] in seen:
                continue
            else:
                seen.add(paper["paper_id"])
            bibtex_entry = f"""@article{{{paper["paper_id"]},
          title = {{{paper["title"]}}},
          author = {{{paper["authors"]}}}, 
          journal={{{paper["journal"]}}}, 
          year = {{{paper["year"]}}}, 
          url = {{{paper["link"]}}}
        }}"""
            bibtex_entries.append(bibtex_entry)
            paper_ids.append(paper["paper_id"])
            # Save the generated BibTeX entries to a file
            with open(path_to_bibtex, "a", encoding="utf-8") as file:
                file.write(bibtex_entry)
                file.write("\n\n")
        return paper_ids

    def _get_papers(self, keyword = "_all"):
        if keyword == "_all":
            papers = []
            for k, v in self.papers.items():
                papers = papers + v
        else:
            papers = self.papers["keyword"]
        return papers

    def to_prompts(self, keyword = "_all"):
        # `prompts`:
        #   {"paper1_bibtex_id": "paper_1_abstract", "paper2_bibtex_id": "paper2_abstract"}
        #   this will be used to instruct GPT model to cite the correct bibtex entry.
        papers = self._get_papers(keyword)
        prompts = {}
        for paper in papers:
            prompts[paper["paper_id"]] = paper["abstract"]
        return prompts

    def to_json(self, keyword = "_all"):
        papers = self._get_papers(keyword)
        papers_json = {}
        for paper in papers:
            papers_json[paper["paper_id"]] = paper
        return papers_json



if __name__ == "__main__":
    # testing search results
    r = ss_search("Deep Q-Networks", limit=1)  # a list of raw papers
    if r['total'] > 0:
        paper = r['data'][0]
        # print(paper)

    # resting References
    refs = References()
    # keywords_dict = {
    #     "Deep Q-Networks": 5,
    #     "Actor-Critic Algorithms": 4,
    #     "Exploration-Exploitation Trade-off": 3
    # }
    # refs.collect_papers(keywords_dict, tldr=True)
    # for k in refs.papers:
    #     papers = refs.papers[k] # for each keyword, there is a list of papers
    #     print("keyword: ", k)
    #     for paper in papers:
    #         print(paper["paper_id"])
    #
    # refs.to_bibtex()
    # papers_json = refs.to_json() # this json can be used to find the most relevant papers
    # with open("papers.json", "w",  encoding='utf-8') as text_file:
    #     text_file.write(f"{papers_json}")
    #
    # prompts = refs.to_prompts()
    # print(prompts)

    bib = "test.bib"
    refs.load_papers(bib, "variance-reduction rl")
    print(refs.papers)

    prompts = refs.to_prompts()
    for k in prompts:
        print(f"{k}: {prompts[k]}\n")
    # for paper in papers:
    #     print(paper)
