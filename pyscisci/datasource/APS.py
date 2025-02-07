import os
import sys
import json
import gzip
import zipfile

import pandas as pd
import numpy as np
from nameparser import HumanName

# determine if we are loading from a jupyter notebook (to make pretty progress bars)
if 'ipykernel' in sys.modules:
    from tqdm.notebook import tqdm
else:
    from tqdm import tqdm

from pyscisci.datasource.readwrite import load_preprocessed_data, load_int, load_float, load_html_str
from pyscisci.database import BibDataBase
from pyscisci.utils import download_file_from_google_drive

# hide this annoying performance warnings
import warnings
warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)


class APS(BibDataBase):
    """
    Base class for APS interface.

    The APS comes as a single xml file.

    You must request usage through their website: https://journals.aps.org/datasets

    """

    def __init__(self, path2database = '', keep_in_memory = False, global_filter=None, show_progress=True):

        self._default_init(path2database, keep_in_memory, global_filter, show_progress)

        self.PublicationIdType = str
        self.AffiliationIdType = str

        


    def preprocess(self, archive_year=2019, pubid2int=False, metadata_archive=None, citation_archive=None, show_progress=True):
        """
        Bulk preprocess the APS raw data.

        """
        if metadata_archive is None:
            metadata_archive = 'aps-dataset-metadata-{}.zip'.format(archive_year)

        self.parse_publications(preprocess=True, preprocess_dicts=True, pubid2int=pubid2int,
            archive_name = metadata_archive, show_progress=show_progress)

        if citation_archive is None:
            citation_archive = 'aps-dataset-citations-{}.zip'.format(archive_year)

        self.parse_references(preprocess=True, pubid2int=pubid2int, archive_name=citation_archive, show_progress=show_progress)



    def download_from_source(self, files_to_download='all'):

        if files_to_download in ['all', 'orig']:
            import webbrowser
            webbrowser.open("https://journals.aps.org/datasets")

            print("APS is shared by request from the American Physical Society.  Contact APS to download the source files.")


        if files_to_download in ['all', 'paa_supplement']:

            aps_author_file_id = '1U6f9AYQJUHQ_IzeiI-rADFsrg7LWH3WO'

            if not os.path.exists(os.path.join(self.path2database, 'publicationauthoraffiliation_supp2010')):
                os.mkdir(os.path.join(self.path2database, 'publicationauthoraffiliation_supp2010'))

            filename = os.path.join(self.path2database, 'publicationauthoraffiliation_supp2010', 'publicationauthoraffiliation_supp20100.hdf')
            apsauthors_gzip = download_file_from_google_drive(file_id=aps_author_file_id, destination= filename)
            pd.read_csv(filename, sep='\t', compression='gzip').to_hdf(filename, mode='w', key='paa')

            self.set_new_data_path(dataframe_name='paa_df', new_path='publicationauthoraffiliation_supp2010')

            print("New data saved to {}.".format('publicationauthoraffiliation_supp2010'))

        if not files_to_download in ['all', 'orig', 'paa_supplement']:
            print("Unrecognized file name.")


    def parse_affiliations(self, preprocess = False, show_progress=False):
        raise NotImplementedError("APS is stored as a json archive.  Run preprocess to parse the archive.")

    def parse_authors(self, preprocess = False, process_name = True, num_file_lines = 5*10**6, show_progress=False):
        raise NotImplementedError("APS does not contain disambiguated author information.")

    def parse_publications(self, preprocess=False, preprocess_dicts=True, pubid2int=False,
        archive_name = 'aps-dataset-metadata-2019.zip', show_progress=False):

        archive = zipfile.ZipFile(os.path.join(self.path2database, archive_name), 'r')
        metadata_files = [fname for fname in archive.namelist() if 'aps-dataset-metadata' in fname and '.json' in fname]

        # check that the archive concatins the expected directory
        if len(metadata_files) > 0:

            if preprocess:

                for hier_dir_type in [self.path2pub_df, self.path2journal_df, self.path2affiliation_df, self.path2paa_df, self.path2pub2field_df, self.path2fieldinfo_df]:

                    if not os.path.exists(os.path.join(self.path2database, hier_dir_type)):
                        os.mkdir(os.path.join(self.path2database, hier_dir_type))


            journal_dict = {}
            journal_column_names = ['JournalId', 'FullName', 'AbbreviatedName', 'Publisher']

            pub_column_names = ['PublicationId', 'Title', 'Date', 'Year', 'Doi', 'JournalId', 'Volume', 'Issue', 'PageStart', 'PageEnd', 'DocType', 'TeamSize']

            pub_df = []
            pub2year = {}
            pub2doctype = {}
            pub2int = {}
            ipub = 0
            if pubid2int:
                pubintcol = ['PublicationId']
                self.PublicationIdType=int
            else:
                pubintcol = []

            iaff = 0
            affil_dict = {}
            paa_df = []

            field_dict = {}
            pub2field_df = []

            for fname in tqdm(metadata_files, desc='aps-metadata', leave=True, disable=not show_progress):
                # load pub json
                pubjson = json.loads(archive.read(fname).decode('utf-8'))
                ipub += 1

                # start parsing publication information
                if pubid2int:
                    pubid = ipub
                    pub2int[pubjson.get('id', '')] = pubid
                else:
                    pubid = pubjson.get('id', '')
                pubinfo = [pubid]
                pubinfo.append(pubjson.get('title', {}).get('value', ''))
                pubinfo.append(pubjson.get('date', ''))
                pubinfo.append(load_int(pubjson.get('date', '').split('-')[0]))
                pub2year[pubid] = pubinfo[-1]
                pubinfo.append(pubjson.get('id', ''))

                # journal of publication
                journalid = pubjson.get('journal', {}).get('id', '')
                pubinfo.append(journalid)
                pubinfo.append(load_int(pubjson.get('volume', {}).get('number', '')))
                pubinfo.append(load_int(pubjson.get('issue', {}).get('number', '')))

                # add pagenumber info
                pubinfo.append(load_int(pubjson.get('pageStart', '')))
                if not pubjson.get('pageEnd', None) is None:
                    pubinfo.append(load_int(pubjson.get('pageEnd', '')))
                elif not (pubjson.get('numPages', None) is None or pubjson.get('pageStart', None) is None):
                    pubinfo.append(pubinfo[-1] + load_int(pubjson.get('numPages', '')))
                else:
                    pubinfo.append(None)

                # add the doctype
                pubinfo.append(pubjson.get('articleType', ''))
                pub2doctype[pubid] = pubinfo[-1]

                # calculate TeamSize
                pubinfo.append(len(pubjson.get('authors', [])))

                # finish publication infor
                pub_df.append(pubinfo)

                # check if we need to save journal information
                if journal_dict.get(journalid, None) is None:
                    journal_dict[journalid] = pubjson.get('journal', {})
                    journal_dict[journalid]['Publisher'] = pubjson.get('rights', {}).get('copyrightHolders', [{'name':''}])[0].get('name', '')

                # start parsing affiliation information
                pub_affid_map = {}
                for pubaffdict in pubjson.get('affiliations', []):
                    # check if the affiliation has been used before (only using string match)
                    # ToDo: add disambigation
                    if affil_dict.get(pubaffdict.get('name', ''), None) is None:
                        affil_dict[pubaffdict.get('name', '')] = iaff
                        iaff += 1

                    # map the affiliation to the AffiliationId
                    pub_affid_map[pubaffdict.get('id', '')] = affil_dict[pubaffdict.get('name', '')]

                authorseq = 1
                # now start parsing author information
                for authordict in pubjson.get('authors', []):
                    for affid in authordict.get('affiliationIds', [None]):
                        paa_df.append([pubid, authordict.get('name', ''), pub_affid_map.get(affid, None), authorseq])

                    authorseq += 1

                classificationschemes = pubjson.get('classificationSchemes', {})

                # now do the subject classifications
                for subjectdict in classificationschemes.get('subjectAreas', []):
                    fid = subjectdict.get('id', None)

                    if not fid is None and len(fid) > 0:
                        pub2field_df.append([pubid, fid])

                        if field_dict.get(fid, None) is None:
                            field_dict[fid] = [subjectdict.get('label', None), 'subjectAreas']

                # now do the subject disciplines
                for subjectdict in classificationschemes.get('physh', {}).get('disciplines', []):
                    fid = subjectdict.get('id', None)

                    if not fid is None and len(fid) > 0:
                        pub2field_df.append([pubid, fid])

                        if field_dict.get(fid, None) is None:
                            field_dict[fid] = [subjectdict.get('label', None), 'disciplines']

                # now do the subject concepts
                for subjectdict in classificationschemes.get('physh', {}).get('concepts', []):
                    fid = subjectdict.get('id', None)

                    if not fid is None and len(fid) > 0:
                        pub2field_df.append([pubid, fid])

                        if field_dict.get(fid, None) is None:
                            field_dict[fid] = [subjectdict.get('label', None), 'concepts']

                    

                # ToDo: parse concepts

            if show_progress:
                print("Parsing Complete\nSaving Publication DataFrames")

            pub_df = pd.DataFrame(pub_df, columns = pub_column_names)
            for intcol in pubintcol + ['Year']:
                pub_df[intcol] = pub_df[intcol].astype(int)

            journal_rename_dict = {'name':'FullName', 'id':'JournalId', 'abbreviatedName':'AbbreviatedName'}
            journal_df = pd.DataFrame(journal_dict.values()).rename(columns=journal_rename_dict)

            affiliation_df = pd.DataFrame([[affid, name] for name, affid in affil_dict.items()], columns = ['AffiliationId', 'Address'])

            paa_df = pd.DataFrame(paa_df, columns = ['PublicationId', 'OrigAuthorName', 'AffiliationId', 'AuthorSequence'])
            for intcol in pubintcol+['AuthorSequence']:
                paa_df[intcol] = paa_df[intcol].astype(int)

            pub2field_df = pd.DataFrame(pub2field_df, columns = ['PublicationId', 'FieldId'])
            for intcol in pubintcol:
                pub2field_df[intcol] = pub2field_df[intcol].astype(int)

            field_df = pd.DataFrame([[fieldid] + fieldname for fieldid, fieldname in field_dict.items()], columns = ['FieldId', 'FullName', 'ClassificationType'])

            if preprocess:
                pub_df.to_hdf(os.path.join(self.path2database, 'publication', 'publication0.hdf'), mode='w', key='publication')

                if pubid2int:
                    with gzip.open(os.path.join(self.path2database, 'pub2int.json.gz'), 'w') as outfile:
                        outfile.write(json.dumps(pub2int).encode('utf8'))

                if preprocess_dicts:
                    with gzip.open(os.path.join(self.path2database, 'pub2year.json.gz'), 'w') as outfile:
                        outfile.write(json.dumps(pub2year).encode('utf8'))

                    with gzip.open(os.path.join(self.path2database, 'pub2doctype.json.gz'), 'w') as outfile:
                        outfile.write(json.dumps(pub2doctype).encode('utf8'))


                journal_df.to_hdf(os.path.join(self.path2database, self.path2journal_df, 'journal0.hdf'), mode='w', key='journal')

                affiliation_df.to_hdf(os.path.join(self.path2database, self.path2affiliation_df, 'affiliation0.hdf'), mode='w', key='affiliation')

                paa_df.to_hdf(os.path.join(self.path2database, self.path2paa_df, 'publicationauthoraffiliation0.hdf'), mode='w', key='publicationauthoraffiliation')

                pub2field_df.to_hdf( os.path.join(self.path2database, self.path2pub2field_df, 'pub2field0.hdf'), mode='w', key='pub2field')

                field_df.to_hdf( os.path.join(self.path2database, self.path2fieldinfo_df, 'fieldinfo0.hdf'), mode='w', key='pub2field')

        else:
            raise FileNotFoundError('The archive {0} does not contain a metadata directory: {1}.'.format(archive_name, 'aps-dataset-metadata'))

    def parse_references(self, preprocess=False, pubid2int=False, archive_name='aps-dataset-citations-2019.zip', show_progress=False):

        if preprocess and not os.path.exists(os.path.join(self.path2database, self.path2pub2ref_df)):
            os.mkdir(os.path.join(self.path2database, self.path2pub2ref_df))

        if pubid2int:
            with gzip.open(os.path.join(self.path2database, 'pub2int.json.gz'), 'r') as infile:
                pub2int = json.loads(infile.read().decode('utf8'))

            def pub2int_map(doi):
                if pub2int.get(doi, None) is None:
                    pub2int[doi] = len(pub2int) + 1

                return pub2int[doi]


        rename_dict = {'citing_doi':'CitingPublicationId', 'cited_doi':'CitedPublicationId'}

        archive = zipfile.ZipFile(os.path.join(self.path2database, archive_name), 'r')

        citation_file = [fname for fname in archive.namelist() if 'aps-dataset-citations' in fname]
        if len(citation_file) > 0:
            citation_file = citation_file[0]
            csvlines = archive.read(citation_file).decode('utf-8').split('\n')

            pub2ref = [line.split(',') for line in tqdm(csvlines, desc='aps-citations', leave=True, disable=not show_progress)]

            pub2ref = pd.DataFrame(pub2ref[1:], columns = pub2ref[0]).rename(columns=rename_dict)
            if pubid2int:
                pub2ref['CitingPublicationId'] = [pub2int_map(pid) for pid in pub2ref['CitingPublicationId'].values]
                pub2ref['CitedPublicationId'] = [pub2int_map(pid) for pid in pub2ref['CitedPublicationId'].values]

                with gzip.open(os.path.join(self.path2database, 'pub2int.json.gz'), 'w') as outfile:
                        outfile.write(json.dumps(pub2int).encode('utf8'))

            if preprocess:
                pub2ref.to_hdf(os.path.join(self.path2database, self.path2pub2ref_df, 'pub2ref0.hdf'), mode='w', key = 'pub2ref')

            return pub2ref

        else:
            raise FileNotFoundError('The archive {0} does not contain a citation file: {1}.'.format(archive_name, 'aps-dataset-citations'))

    def parse_publicationauthoraffiliation(self, preprocess = False, num_file_lines=10**7, show_progress=False):
        raise NotImplementedError("APS is stored as a json archive.  Run preprocess to parse the archive.")

    def parse_fields(self, preprocess = False, num_file_lines=10**7, show_progress=False):
        raise NotImplementedError("APS is stored as a json archive.  Run preprocess to parse the archive.")

