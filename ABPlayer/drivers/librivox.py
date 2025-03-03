import typing as ty
from internetarchive import files
from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, hms2sec, html2text, dlink_maker
import time
import internetarchive as ia
gethits=ia.api.search_items

class LibriVox(Driver):
    site_url = "https://archive.org/download/"
    
    downloader_factory = MP3Downloader

    def get_book(self, url: str) -> Book:
        """
        fetches book from internetarchive using the identifier
        
        """
        identifier=url.split('/')[-1]
        print(f"print(identifier):{identifier}")
        ia_bookObj=ia.get_item(identifier)
        author=ia_bookObj.metadata['creator']
        title=ia_bookObj.metadata['title']
        duration=hms2sec(ia_bookObj.metadata['runtime'])
        description=html2text(ia_bookObj.metadata['description'])
        cover_filename=vars(list(ia_bookObj.get_files(formats="JPEG"))[0])['name'].strip()
        preview=dlink_maker(self.site_url,identifier,cover_filename) #entering URL explicitly now for the sake of debugging
        chapters=BookItems()
        audiofiles=self.fobj2list(ia_bookObj.get_files(formats=['64Kbps MP3']))
        for file in audiofiles:
            if file['format']=='64Kbps MP3':
                chapters.append(
                    BookItem(
                        file_url=dlink_maker(self.site_url,identifier,file['name']), #explicit
                        file_index=int(file['track'].strip(' ')) if('track' in file.keys()) else 0,
                        title=file['title'] ,
                        start_time=0 ,
                        end_time=hms2sec(file['length'])
                    ))
        book=Book(
            author=safe_name(author),
            name=safe_name(title),
            series_name=None,
            number_in_series=None,
            description=description,
            reader="field not available(sorry)",
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=chapters,
        )
        return book

    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        """
        for now I have no idea how to paginate so paginate(offset) and limit are not implemented
        I am yet to find a way to limit how many results are returned by internetarchive.search_items()
        """
        books = []
        hits=ia.search_items(f'title:({query}) AND collection:librivoxaudio')
        #compensating for limit and offset
        hits=list(hits) #converting internet archive's custom list object  (search) to simple list object 
        hits=hits[offset:offset+limit]
        #time.sleep(0.1)#accepted rate limit is 5-10 requests
        if len(hits)>0:  
            for i in hits:
                identifier=i['identifier']
                ia_bookObj=ia.get_item(identifier)
                author=ia_bookObj.metadata['creator']
                name=ia_bookObj.metadata['title']
                duration=ia_bookObj.metadata['runtime']
                coverImg= self.fobj2list(ia_bookObj.get_files(formats="JPEG"))[0]['name']
                preview=self.download_link(identifier,coverImg)
                books.append(
                            Book(
                                author=safe_name(author),
                                name=safe_name(name),
                                duration=duration,
                                url=f'{self.site_url}{identifier}',
                                preview=preview,
                                driver=self.driver_name,
                            )
                        )
                #time.sleep(0.1)
        return books


    def fobj2list(self, ia_files):
        """
        
        Accepts the output of ia_item.get_files.
        Returns a list of dictionaries of attributes of the file objects.

        """
        temp = list(ia_files)
        files_list = []
        for file in temp:
            files_list.append(vars(file))
        return files_list

    def get_book_series(self, url: str) -> ty.List[Book]:
        """
        to be implemented
        """
        books=ty.List()
        return books
    

    def download_link(self, identifier:str,filename: str) -> str:
        """
        returns download endpoint for provided filename.
        """
        url=f"https://archive.org/download/{identifier.strip(' ')}/{filename.strip(' ')}"
        return url