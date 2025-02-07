# -*- coding: utf-8 -*-
"""
.. module:: datasource
    :synopsis: Set of classes to work with different bibliometric data sources

.. moduleauthor:: Alex Gates <ajgates42@gmail.com>
 """

import os
import json
import gzip
from collections import defaultdict

import pandas as pd
import numpy as np
from nameparser import HumanName

from pyscisci.utils import isin_sorted, zip2dict, load_int, load_float, groupby_count
from pyscisci.metrics import *
from pyscisci.datasource.readwrite import load_preprocessed_data, append_to_preprocessed_df
from pyscisci.filter import *

class BibDataBase(object):
    """
    Base class for all bibliometric database interfaces.

    The BibDataBase provides a parasomonious structure for each of the specific data sources (MAG, WOS, etc.).

    There are four primary types of functions:
        1. *Parseing* Functions (data source specific) that parse the raw data files
        2. *Loading* Functions that load DataFrames
        3. *Processing* Functions that calculate advanced data types from the raw files
        4. *Analysis* Functions that calculate Science of Science metrics.

    |

    Parameters
    -------

    path2database: str
        The path to the database files

    keep_in_memory: bool, default False
        Flag to keep database files in memory once loaded

    global_filter: dict or Filter
        Set of conditions to apply globally.

    show_progress: bool, default True
        Flag to show progress of loading, processing, and calculations.
    

    |


    """

    def __init__(self, path2database = '', keep_in_memory = False, global_filter = None, show_progress=True):

        self._default_init(path2database, keep_in_memory, global_filter, show_progress)
        

    def _default_init(self, path2database = '', keep_in_memory = False, global_filter = None, show_progress=True):
        self.path2database = path2database
        self.keep_in_memory = keep_in_memory
        self.global_filter = None
        self.show_progress = show_progress

        self.path2author_df = 'author'
        self.path2pub_df = 'publication'
        self.path2affiliation_df = 'affiliation'
        self.path2pub2ref_df = 'pub2ref'
        self.path2paa_df = 'publicationauthoraffiliation'
        self.path2pub2field_df = 'pub2field'
        self.path2journal_df = 'journal'
        self.path2fieldinfo_df = 'fieldinfo'
        self.path2impact_df = 'impact'

        self._affiliation_df = None
        self._pub_df = None
        self._journal_df = None
        self._author_df = None
        self._pub2year = None
        self._pub2doctype = None
        self._pub2ref_df = None
        self._author2pub_df = None
        self._paa_df = None
        self._pub2refnoself_df = None
        self._pub2field_df=None
        self._fieldinfo_df = None

        self.PublicationIdType = int
        self.AffiliationIdType = int
        self.AuthorIdType = int

        if not global_filter is None:
            self.set_global_filters(global_filter)

    def set_new_data_path(self, dataframe_name='', new_path=''):
        if dataframe_name == 'author_df':
            self.path2author_df = new_path
        elif dataframe_name == 'pub_df':
            self.path2pub_df = new_path
        elif dataframe_name == 'affiliation_df':
            self.path2affiliation_df = new_path
        elif dataframe_name == 'pub2ref_df':
            self.path2pub2ref_df = new_path
        elif dataframe_name == 'paa_df':
            self.path2paa_df = new_path
        elif dataframe_name == 'pub2field_df':
            self.path2pub2field_df = new_path
        elif dataframe_name == 'fieldinfo_df':
            self.path2fieldinfo_df = new_path
        elif dataframe_name == 'journal_df':
            self.path2journal_df = new_path
        elif dataframe_name == 'impact_df':
            self.path2impact_df = new_path
        else:
            print("Unrecognized DataFrame {}".format(dataframe_name))

    @property
    def affiliation_df(self):
        """
        The DataFrame keeping affiliation information. Columns may depend on the specific datasource.

        Notes
        --------
        columns: 'AffiliationId', 'NumberPublications', 'NumberCitations', 'FullName', 'GridId', 'OfficialPage', 'WikiPage', 'Latitude', 'Longitude'

        
        |

        """
        if self._affiliation_df is None:
            if self.keep_in_memory:
                self._affiliation_df = self.load_affiliations(show_progress=self.show_progress)
            else:
                return self.load_affiliations(show_progress=self.show_progress)

        return self._affiliation_df


    @property
    def author_df(self):
        """
        The DataFrame keeping author information. Columns may depend on the specific datasource.

        Notes
        --------
        columns: 'AuthorId', 'LastKnownAffiliationId', 'NumberPublications', 'NumberCitations', 'FullName', 'LastName', 'FirstName', 'MiddleName'


        |

        """
        if self._author_df is None:
            if self.keep_in_memory:
                self._author_df = self.load_authors(show_progress=self.show_progress)
            else:
                return self.load_authors(show_progress=self.show_progress)

        return self._author_df

    @property
    def pub_df(self):
        """
        The DataFrame keeping publication information. Columns may depend on the specific datasource.

        Notes
        -------
        columns: 'PublicationId', 'Year', 'JournalId', 'FamilyId', 'Doi', 'Title', 'Date', 'Volume', 'Issue', 'DocType'

        
        |

        """
        if self._pub_df is None:
            if self.keep_in_memory:
                self._pub_df = self.load_publications(show_progress=self.show_progress)
            else:
                return self.load_publications(show_progress=self.show_progress)

        return self._pub_df

    @property
    def pub2year(self):
        """
        A dictionary mapping PublicationId to Year.

        """
        if self._pub2year is None:
            if self.keep_in_memory:
                self._pub2year = self.load_pub2year()
            else:
                return self.load_pub2year()

        return self._pub2year

    @property
    def pub2doctype(self):
        """
        A dictionary mapping PublicationId to Document Type.
        
        Notes
        -------
        doctype mapping: 'Journal': 'j', 'Book':'b', '':'', 'BookChapter':'bc', 'Conference':'c', 'Dataset':'d', 'Patent':'p', 'Repository':'r'
        
        |

        """
        if self._pub2doctype is None:
            if self.keep_in_memory:
                self._pub2doctype = self.load_pub2doctype()
            else:
                return self.load_pub2doctype()

        return self._pub2doctype

    @property
    def journal_df(self):
        """
        The DataFrame keeping journal information.  Columns may depend on the specific datasource.

        Notes
        -------
        columns: 'JournalId', 'FullName', 'Issn', 'Publisher', 'Webpage'
        
        |

        """
        if self._journal_df is None:
            if self.keep_in_memory:
                self._journal_df = self.load_journals(show_progress=self.show_progress)
            else:
                return self.load_journals(show_progress=self.show_progress)

        return self._journal_df

    @property
    def pub2ref_df(self):
        """
        The DataFrame keeping citing and cited PublicationId.

        Notes
        -------
        columns: 'CitingPublicationId', 'CitedPublicationId'
        
        |

        """
        if self._pub2ref_df is None:
            if self.keep_in_memory:
                self._pub2ref_df = self.load_references(show_progress=self.show_progress)
            else:
                return self.load_references(show_progress=self.show_progress)

        return self._pub2ref_df

    @property
    def pub2refnoself_df(self):
        """
        The DataFrame keeping citing and cited PublicationId after filtering out the self-citations.

        Notes
        -------
        columns: CitingPublicationId, CitedPublicationId
        
        |

        """
        if self._pub2refnoself_df is None:
            if self.keep_in_memory:
                self._pub2refnoself_df = self.load_references(noselfcite=True, show_progress=self.show_progress)
            else:
                return self.load_references(noselfcite=True, show_progress=self.show_progress)

        return self._pub2refnoself_df

    @property
    def paa_df(self):
        """
        The DataFrame keeping all publication, author, affiliation relationships.  Columns may depend on the specific datasource.

        Notes
        -------
        columns: 'PublicationId', 'AuthorId', 'AffiliationId', 'AuthorSequence',  'OrigAuthorName', 'OrigAffiliationName'
        
        |

        """
        if self._paa_df is None:
            if self.keep_in_memory:
                self._paa_df = self.load_publicationauthoraffiliation(show_progress=self.show_progress)
            else:
                return self.load_publicationauthoraffiliation(show_progress=self.show_progress)

        return self._paa_df

    @property
    def author2pub_df(self):
        """
        The DataFrame keeping all publication, author relationships.  Columns may depend on the specific datasource.

        Notes
        -------
        columns: 'PublicationId', 'AuthorId'
        
        |

        """
        if self._paa_df is None:
            if self.keep_in_memory:
                self._paa_df = self.load_publicationauthoraffiliation(columns = ['AuthorId', 'PublicationId'],
                    duplicate_subset = ['AuthorId', 'PublicationId'], dropna = ['AuthorId', 'PublicationId'], show_progress=self.show_progress)
            else:
                return self.load_publicationauthoraffiliation(columns = ['AuthorId', 'PublicationId'],
                    duplicate_subset = ['AuthorId', 'PublicationId'], dropna = ['AuthorId', 'PublicationId'], show_progress=self.show_progress)

        return self._paa_df

    @property
    def pub2field_df(self):
        """
        The DataFrame keeping all publication field relationships.  Columns may depend on the specific datasource.

        Notes
        -------
        columns: 'PublicationId', 'FieldId'
        
        |

        """

        if self._pub2field_df is None:
            if self.keep_in_memory:
                self._pub2field_df = self.load_pub2field(show_progress=self.show_progress)
            else:
                return self.load_pub2field(show_progress=self.show_progress)

        return self._pub2field_df

    @property
    def fieldinfo_df(self):
        """
        The DataFrame keeping all publication field relationships.  Columns may depend on the specific datasource.

        Notes
        -------
        columns: 'FieldId', 'FieldLevel', 'NumberPublications', 'FieldName'
        
        |

        """
        if self._fieldinfo_df is None:
            if self.keep_in_memory:
                self._fieldinfo_df = self.load_fieldinfo(show_progress=self.show_progress)
            else:
                return self.load_fieldinfo(show_progress=self.show_progress)

        return self._fieldinfo_df

    def publicationid_list(self):
        """
        A list of all PublicationIds.
        

        |

        """
        if self.global_filter is None:
            return sorted(list(self.load_publications(columns=['PublicationId'], duplicate_subset=['PublicationId'])['PublicationId'].unique()))

        else:
            return sorted(list(self.global_filter))


    def set_global_filters(self, global_filter):
        """
        Set of filtering conditions that restrict the global set of publications loaded from the DataBase.

        Allowable global filters are:
            'Year', 'DocType', 'FieldId'
        

        |

        """

        if isinstance(global_filter, list):
            filter_dict = {f.field:f for f in global_filter}

        elif isinstance(global_filter, (RangeFilter, YearFilter, SetFilter, DocTypeFilter, FieldFilter) ):
            filter_dict = { global_filter.field:global_filter}

        elif type(global_filter) is dict:
            filter_dict = global_filter

        else:
            raise TypeError("global_filter must be a single pyscisci Filter, a list of pyscisci Filters, or a dictionary of pyscisci Filters.")

        # to create a global filter across all dataframes, we need to create a list of the allowable PublicationIds
        
        for filtertype, pubfilter in filter_dict.items():
            if filtertype == 'Year':
                pub2year = self.pub2year

                if self.global_filter is None:
                    self.global_filter = {pid for pid, y in pub2year.items() if filter_dict['Year'].check_value(y)}
                else:
                    self.global_filter = {pid for pid in self.global_filter if not pub2year.get(pid, None) is None and filter_dict['Year'].check_value(pub2year[pid])}

            elif filtertype == 'DocType':
                pub2doctype = self.pub2doctype
                
                if self.global_filter is None:
                    self.global_filter = {pid for pid, dt in pub2doctype.items() if filter_dict['DocType'].check_value(dt)}
                else:
                    self.global_filter = {pid for pid in self.global_filter if not pub2doctype.get(pid, None) is None and filter_dict['DocType'].check_value(pub2doctype[pid])}

            elif filtertype == 'FieldId':

                if self.global_filter is None:
                    load_fields_filter = {'FieldId':np.sort(list(filter_dict['FieldId'].value_set))}

                else:
                    load_fields_filter = {'FieldId':np.sort(list(filter_dict['FieldId'].value_set)), 'PublicationId':np.sort(list(self.global_filter))}

                pub2field = self.load_pub2field(columns = ['PublicationId', 'FieldId'], filter_dict = load_fields_filter)

                self.global_filter = set(pub2field['PublicationId'].unique())

            else:
                raise TypeError("{} is not a valid global filter.  It must be one of 'Year', 'DocType', 'FieldId'.".format(filtertype))


    ## Basic Functions for loading data from either preprocessed sources or the raw database files

    def load_affiliations(self, preprocess = True, columns = None, filter_dict = None, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the Affiliation DataFrame from a preprocessed directory, or parse from the raw files.
        

        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default None, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns
        
   
        Returns
        -------
        DataFrame
            Affililation DataFrame.
        

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Affiliations'

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2affiliation_df)):
            return load_preprocessed_data(self.path2affiliation_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_affiliations()

    def load_authors(self, preprocess = True, columns = None, filter_dict = None, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, process_name = True, show_progress=True):
        """
        Load the Author DataFrame from a preprocessed directory, or parse from the raw files.


        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default None, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        process_name : bool, default True, Optional
            If True, then when processing the raw file, the package `NameParser <https://nameparser.readthedocs.io/en/latest/>`_
            will be used to split author FullNames.


        Returns
        -------
        DataFrame
            Author DataFrame.
        

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Authors'

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2author_df)):
            return load_preprocessed_data(self.path2author_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_authors(process_name=process_name)

    def load_publications(self, preprocess = True, columns = None, filter_dict = None, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the Publication DataFrame from a preprocessed directory, or parse from the raw files.


        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default None, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns


        Returns
        -------
        DataFrame
            Publication DataFrame.


        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Publications'

        if not self.global_filter is None:
            if 'PublicationId' in filter_dict:
                filter_dict['PublicationId'] = np.sort([pid for pid in filter_dict['PublicationId'] if pid in self.global_filter])
            else:
                filter_dict['PublicationId'] = np.sort(list(self.global_filter))

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2pub_df)):
            return load_preprocessed_data(dataname=self.path2pub_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_publications()

    def load_pub2year(self):

        if os.path.exists(os.path.join(self.path2database, 'pub2year.json.gz')):
            with gzip.open(os.path.join(self.path2database, 'pub2year.json.gz'), 'r') as infile:
                pub2year = json.loads(infile.read().decode('utf8'))
            return {self.PublicationIdType(k):int(y) for k,y in pub2year.items() if not y is None}

    def load_pub2doctype(self):
        if os.path.exists(os.path.join(self.path2database, 'pub2doctype.json.gz')):
            with gzip.open(os.path.join(self.path2database, 'pub2doctype.json.gz'), 'r') as infile:
                pub2doctype = json.loads(infile.read().decode('utf8'))
            return {self.PublicationIdType(k):dt for k,dt in pub2doctype.items() if not dt is None}

    def load_journals(self, preprocess = True, columns = None, filter_dict = None, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the Journal DataFrame from a preprocessed directory, or parse from the raw files.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default None, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        Returns
        -------
        DataFrame
            Journal DataFrame.
        

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Journals'

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2journal_df)):
            return load_preprocessed_data(self.path2journal_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_publications()

    def load_references(self, preprocess = True, columns = None, filter_dict = {}, duplicate_subset = None,
        duplicate_keep = 'last', noselfcite = False, dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the Pub2Ref DataFrame from a preprocessed directory, or parse from the raw files.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default {}, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        noselfcite : bool, default False, Optional
            If True, then the preprocessed pub2ref files with self-citations removed will be used.

        Returns
        -------
        DataFrame
            Pub2Ref DataFrame.
        

        |

        """
        if noselfcite:
            fileprefix = self.path2pub2ref_df + 'noself'
        else:
            fileprefix = self.path2pub2ref_df

        if not self.global_filter is None:
            if 'CitingPublicationId' in filter_dict:
                filter_dict['CitingPublicationId'] = np.sort([pid for pid in filter_dict['CitingPublicationId'] if pid in self.global_filter])
            else:
                filter_dict['CitingPublicationId'] = np.sort(list(self.global_filter))

            if 'CitedPublicationId' in filter_dict:
                filter_dict['CitedPublicationId'] = np.sort([pid for pid in filter_dict['CitedPublicationId'] if pid in self.global_filter])
            else:
                filter_dict['CitedPublicationId'] = np.sort(list(self.global_filter))

        if show_progress or self.show_progress:
            show_progress='Loading {}'.format(fileprefix)

        if preprocess and os.path.exists(os.path.join(self.path2database, fileprefix)):
            return load_preprocessed_data(fileprefix, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_references()

    def load_publicationauthoraffiliation(self, preprocess = True, columns = None, filter_dict = {}, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the PublicationAuthorAffilation DataFrame from a preprocessed directory, or parse from the raw files.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default {}, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        Returns
        -------
        DataFrame
            PublicationAuthorAffilation DataFrame.
        

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Publication Author Affiliation'

        if not self.global_filter is None:
            if 'PublicationId' in filter_dict:
                filter_dict['PublicationId'] = np.sort([pid for pid in filter_dict['PublicationId'] if pid in self.global_filter])
            else:
                filter_dict['PublicationId'] = np.sort(list(self.global_filter))

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2paa_df)):
            return load_preprocessed_data(self.path2paa_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_publicationauthoraffiliation()

    def load_pub2field(self, preprocess = True, columns = None, filter_dict = {}, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the Pub2Field DataFrame from a preprocessed directory, or parse from the raw files.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default {}, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        Returns
        -------
        DataFrame
            Pub2Field DataFrame.
        

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Fields'

        if not self.global_filter is None:
            if 'PublicationId' in filter_dict:
                filter_dict['PublicationId'] = np.sort([pid for pid in filter_dict['PublicationId'] if pid in self.global_filter])
            else:
                filter_dict['PublicationId'] = np.sort(list(self.global_filter))

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2pub2field_df)):
            return load_preprocessed_data(self.path2pub2field_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=prefunc2apply, postfunc2apply=postfunc2apply, show_progress=show_progress)
        else:
            return self.parse_fields()

    def load_fieldinfo(self, preprocess = True, columns = None, filter_dict = {}, show_progress=False):
        """
        Load the Field Information DataFrame from a preprocessed directory, or parse from the raw files.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            Attempt to load from the preprocessed directory.

        columns : list, default None, Optional
            Load only this subset of columns

        filter_dict : dict, default {}, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        Returns
        -------
        DataFrame
            FieldInformation DataFrame.
    

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Field Info'

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2fieldinfo_df)):
            return pd.read_hdf(os.path.join(self.path2database, self.path2fieldinfo_df, 'fieldinfo0.hdf'))
        else:
            return self.parse_fields()

    def load_impact(self, preprocess = True, include_yearnormed = True, columns = None, filter_dict = {}, duplicate_subset = None,
        duplicate_keep = 'last', dropna = None, prefunc2apply=None, postfunc2apply=None, show_progress=False):
        """
        Load the precomputed impact DataFrame from a preprocessed directory.

        Parameters
        ----------
        preprocess : bool, default True
            Attempt to load from the preprocessed directory.

        include_yearnormed: bool, default True
            Normalize all columns by yearly average.

        columns : list, default None
            Load only this subset of columns

        filter_dict : dict, default {}, Optional
            Dictionary of format {"ColumnName":"ListofValues"} where "ColumnName" is a data column
            and "ListofValues" is a sorted list of valid values.  A DataFrame only containing rows that appear in
            "ListofValues" will be returned.

        duplicate_subset : list, default None, Optional
            Drop any duplicate entries as specified by this subset of columns

        duplicate_keep : str, default 'last', Optional
            If duplicates are being dropped, keep the 'first' or 'last'
            (see `pandas.DataFram.drop_duplicates <https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.drop_duplicates.html>`_)

        dropna : list, default None, Optional
            Drop any NaN entries as specified by this subset of columns

        Returns
        -------
        DataFrame
            FieldInformation DataFrame.
        

        |

        """
        if show_progress or self.show_progress:
            show_progress='Loading Impact'

        if not self.global_filter is None:
            if 'PublicationId' in filter_dict:
                filter_dict['PublicationId'] = np.sort([pid for pid in filter_dict['PublicationId'] if pid in self.global_filter])
            else:
                filter_dict['PublicationId'] = np.sort(list(self.global_filter))

        if include_yearnormed:
            def normfunc(impactdf):
                impactcolumns = [c for c in list(impactdf) if not c in ['PublicationId', 'Year']]
                for c in impactcolumns:
                    impactdf[c+'_norm'] = impactdf[c]/impactdf[c].mean()
                return impactdf
        else:
            def normfunc(impactdf):
                return impactdf

        if preprocess and os.path.exists(os.path.join(self.path2database, self.path2impact_df)):
            return load_preprocessed_data(self.path2impact_df, path2database=self.path2database, columns=columns,
                filter_dict=filter_dict, duplicate_subset=duplicate_subset, duplicate_keep=duplicate_keep, dropna=dropna,
                prefunc2apply=normfunc, show_progress=show_progress)
        else:
            raise self.compute_impact()

    """
    To be rewritten for each specific data source (MAG, WOS, etc.)
    """

    def download_from_source(self):
        raise NotImplementedError

    def parse_affiliations(self, preprocess = False):
        raise NotImplementedError

    def parse_authors(self, preprocess = False, process_name = True, num_file_lines = 5*10**6):
        raise NotImplementedError

    def parse_publications(self, preprocess = False, num_file_lines=10**7):
        raise NotImplementedError

    def parse_references(self, preprocess = False, num_file_lines=10**7):
        raise NotImplementedError

    def parse_publicationauthoraffiliation(self, preprocess = False, num_file_lines=10**7):
        raise NotImplementedError

    def parse_fields(self, preprocess = False, num_file_lines=10**7):
        raise NotImplementedError

    def remove_selfcitations(self, preprocess=True, show_progress=False):
        """
        Prcoess the pub2ref DataFrame and remove all citation relationships that share an Author.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            If True then the new preprocessed DataFrames are saved in pub2refnoself

        Returns
        -------
        DataFrame
            Pub2Ref DataFrame with 2 columns: 'CitingPublicationId', 'CitedPublicationId'
        
        |

        """
        if self.show_progress:
            show_progress=True

        if preprocess:
            if not os.path.exists(os.path.join(self.path2database, 'pub2refnoself')):
                os.mkdir(os.path.join(self.path2database, 'pub2refnoself'))

        pub2authors = defaultdict(set)
        for pid, aid in self.author2pub_df[['PublicationId', 'AuthorId']].values:
            pub2authors[pid].add(aid)

        fullrefdf = []
        # loop through all pub2ref files
        Nreffiles = sum('pub2ref' in fname for fname in os.listdir(os.path.join(self.path2database, 'pub2ref')))
        for ifile in tqdm(range(Nreffiles), desc='Removing Self-citations', disable= not show_progress):
            refdf = pd.read_hdf(os.path.join(self.path2database, 'pub2ref', 'pub2ref{}.hdf'.format(ifile)))

            # get citing cited pairs with no common authors
            noselfcite = np.array([len(pub2authors[citingpid] & pub2authors[citedpid]) == 0 for citingpid, citedpid in refdf.values])

            # keep only citing-cited pairs without a common author
            refdf = refdf.loc[noselfcite]

            if preprocess:
                refdf.to_hdf(os.path.join(self.path2database, 'pub2refnoself', 'pub2refnoself{}.hdf'.format(ifile)), key = 'pub2ref')
            else:
                fullrefdf.append(refdf)

        if not preprocess:
            return pd.concat(fullrefdf)


    def compute_impact(self, preprocess=True, citation_horizons = [5,10], noselfcite = True):
        """
        Calculate several of the common citation indices.
            * 'Ctotal' : The total number of citations.
            * 'Ck' : The total number of citations within the first k years of publcation, for each k value specified by `citation_horizons`.
            * 'Ctotal_noself' : The total number of citations with self-citations removed.
            * 'Ck' : The total number of citations within the first k years of publcation with self-citations removed, for each k value specified by `citation_horizons`.

        Parameters
        ----------
        preprocess : bool, default True, Optional
            If True then the impact measures are saved in preprocessed files.

        citation_horizons : list, default [5,10], Optional
            The DataFrame column with Author Ids.  If None then the database 'AuthorId' is used.

        noselfcite : Bool, default 'True', Optional
            If True then the noselfcitation pub2ref files are also processed.

        Returns
        -------
        DataFrame
            The impact DataFrame with at least two columns: 'PublicationId', 'Year', + citation columns
        

        |

        """

        # first load the publication year information
        pub2year = self.load_pub2year()

        # now get the reference list and merge with year info
        pub2ref = self.pub2ref_df

        # drop all citations that happend before the publication year
        pub2ref = pub2ref.loc[[pub2year.get(citingpid, 0) >= pub2year.get(citedpid, 0) for citingpid, citedpid in pub2ref[['CitingPublicationId', 'CitedPublicationId']].values]]

        # calcuate the total citations
        citation_df = groupby_count(pub2ref, colgroupby='CitedPublicationId', colcountby='CitingPublicationId', count_unique=True )
        citation_df.rename(columns={'CitingPublicationIdCount':'Ctotal', 'CitedPublicationId':'PublicationId'}, inplace=True)

        # go from the larest k down
        for k in np.sort(citation_horizons)[::-1]:

            # drop all citations that happend after the k
            #pub2ref = pub2ref.loc[pub2ref['CitingPublicationYear'] <= pub2ref['CitedPublicationYear'] + k]
            pub2ref = pub2ref.loc[[pub2year.get(citingpid, 0) <= pub2year.get(citedpid, 0) + k for citingpid, citedpid in pub2ref[['CitingPublicationId', 'CitedPublicationId']].values]]

            # recalculate the impact
            k_citation_df = groupby_count(pub2ref, colgroupby='CitedPublicationId', colcountby='CitingPublicationId', count_unique=True )
            k_citation_df.rename(columns={'CitingPublicationIdCount':'C{}'.format(k), 'CitedPublicationId':'PublicationId'}, inplace=True)

            citation_df = citation_df.merge(k_citation_df, how='left', on='PublicationId')

        # get the Cited Year
        citation_df['Year'] = [pub2year.get(pid, 0) for pid in citation_df['PublicationId'].values]


        if noselfcite:
            del pub2ref
            pub2ref = self.pub2refnoself_df

            # drop all citations that happend before the publication year
            pub2ref = pub2ref.loc[[pub2year.get(citingpid, 0) >= pub2year.get(citedpid, 0) for citingpid, citedpid in pub2ref[['CitingPublicationId', 'CitedPublicationId']].values]]

            # calcuate the total citations
            citation_noself_df = groupby_count(pub2ref, colgroupby='CitedPublicationId', colcountby='CitingPublicationId', count_unique=True )
            citation_noself_df.rename(columns={'CitingPublicationIdCount':'Ctotal_noself', 'CitedPublicationId':'PublicationId'}, inplace=True)

            # go from the larest k down
            for k in np.sort(citation_horizons)[::-1]:

                # drop all citations that happend after the k
                #pub2ref = pub2ref.loc[pub2ref['CitingPublicationYear'] <= pub2ref['CitedPublicationYear'] + k]
                pub2ref = pub2ref.loc[[pub2year.get(citingpid, 0) <= pub2year.get(citedpid, 0) + k for citingpid, citedpid in pub2ref[['CitingPublicationId', 'CitedPublicationId']].values]]

                # recalculate the impact
                k_citation_df = groupby_count(pub2ref, colgroupby='CitedPublicationId', colcountby='CitingPublicationId', count_unique=True )
                k_citation_df.rename(columns={'CitingPublicationIdCount':'C{}_noself'.format(k), 'CitedPublicationId':'PublicationId'}, inplace=True)

                citation_noself_df = citation_noself_df.merge(k_citation_df, how='left', on='PublicationId')

            citation_df = citation_df.merge(citation_noself_df, how='left', on='PublicationId')

        # set all nan to 0
        citation_df.fillna(0, inplace=True)

        if preprocess:

            if not os.path.exists(os.path.join(self.path2database, 'impact')):
                os.mkdir(os.path.join(self.path2database, 'impact'))

            for y, cdf in citation_df.groupby('Year', sort=True):
                cdf.to_hdf(os.path.join(self.path2database, 'impact', 'impact{}.hdf'.format(y)), mode='w', key ='impact')

        else:
            return citation_df




    def compute_teamsize(self, save2pubdf = True, show_progress=False):
        """
        Calculate the teamsize of publications, defined as the total number of Authors on the publication.

        Parameters
        ----------
        save2pubdf : bool, default True, Optional
            If True the results are appended to the preprocessed publication DataFrames.

        show_progress: bool, default False
            If True, display a progress bar for the count.

        Returns
        -------
        DataFrame
            TeamSize DataFrame with 2 columns: 'PublicationId', 'TeamSize'
        
        
        |

        """
        if show_progress or self.show_progress: 
            print("Starting TeamSize computation. \nLoading Data.")

        pub2authorseq_df = self.load_publicationauthoraffiliation(columns = ['PublicationId', 'AuthorId', 'AuthorSequence'],
            duplicate_subset = ['PublicationId', 'AuthorId'], dropna = ['PublicationId', 'AuthorId'])

        # register our pandas apply with tqdm for a progress bar
        tqdm.pandas(desc='TeamSize', disable= not show_progress)

        pub2teamsize = pub2authorseq_df.groupby('PublicationId', sort=False)['AuthorSequence'].progress_apply(lambda x: x.max()).astype(int).to_frame().reset_index().rename(columns={'AuthorSequence':'TeamSize'})

        if save2pubdf:
            if show_progress: print("Saving Teamsize.")
            append_to_preprocessed_df(pub2teamsize, self.path2database, 'publication')

        return pub2teamsize


    def compute_yearly_citations(self, preprocess = True, show_progress=False):

        if show_progress:
            print("Starting Computation of Yearly Citations")

        # first load the publication year information
        pub2year = self.pub2year

        # now get the reference list and merge with year info
        pub2ref = self.pub2ref_df

        pub2ref['CitingYear'] = [pub2year.get(citingpid, 0) for citingpid in pub2ref['CitingPublicationId'].values]

        # drop all citations that happend before the publication year
        pub2ref = pub2ref.loc[[citingyear >= pub2year.get(citedpid, 0) for citingyear, citedpid in pub2ref[['CitingYear', 'CitedPublicationId']].values]]

        if show_progress:
            print("Yearly Citation Data Prepared")

        # calcuate the total citations
        citation_df = groupby_count(pub2ref, colgroupby=['CitedPublicationId', 'CitingYear'], colcountby='CitingPublicationId', count_unique=True )
        citation_df.rename(columns={'CitingPublicationIdCount':'YearlyCitations', 'CitedPublicationId':'PublicationId'}, inplace=True)

        # get the Cited Year
        citation_df['CitedYear'] = [pub2year.get(pid, 0) for pid in citation_df['PublicationId'].values]

        citation_df.sort_values(by=['CitedYear', 'CitedPublicationId', 'CitingYear'], inplace=True)

        if show_progress:
            print("Yearly Citations Found")

        if preprocess:
            if not os.path.exists(os.path.join(self.path2database, 'temporalimpact')):
                os.mkdir(os.path.join(self.path2database, 'temporalimpact'))

            for y, cdf in citation_df.groupby('CitedYear', sort=True):
                cdf.to_hdf(os.path.join(self.path2database, 'temporalimpact', 'temporalimpact{}.hdf'.format(y)), mode='w', key ='temporalimpact')

            if show_progress:
                print("Yearly Citations Saved")

        else:
            return citation_df

