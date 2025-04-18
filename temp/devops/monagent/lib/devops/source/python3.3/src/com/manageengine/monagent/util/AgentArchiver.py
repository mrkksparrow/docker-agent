#$Id$
import tarfile

ZIP=1
TAR=2

ARCHIVER_FACTORY = None

def initialize():
    global ARCHIVER_FACTORY
    ARCHIVER_FACTORY = ArchiverFactory()
    
def getArchiver(archiveConstant):
    return ARCHIVER_FACTORY.getArchiver(archiveConstant)
    
class ArchiverFactory(object):
    def getArchiver(self, archiveConstant):
        if archiveConstant == TAR:
            return TarHandler()
        elif archiveConstant == ZIP:
            return ZipHandler()
        
class ZipHandler(object):
    pass

class TarHandler(object):
    def __init__(self):     
        self.file = None
        self.handle = None
        self.mode = 'r'
        self.path = None
        self.folder = None        
    def __str__(self):
        str_tarProps = ''
        str_tarProps = str_tarProps + 'File : '+repr(self.file)
        str_tarProps = str_tarProps + ' Mode : '+repr(self.mode)+'\n'
        str_tarProps = str_tarProps + ' Path : '+repr(self.path)+'\n'
        str_tarProps = str_tarProps + ' Folder : '+repr(self.folder)+'\n'        
        return str_tarProps
    def compress(self):
        pass    
    def decompress(self):
        try:
            def getFileList():
                if self.folder == None:
                    for tarinfo in self.handle:                
                        yield tarinfo
                else:
                    for tarinfo in self.handle:                        
                        if tarinfo.name.startswith(self.folder) and tarinfo.name.rfind('/') != -1:
                            yield tarinfo
            def extract():                
                fileList = getFileList()    
                self.handle.extractall(self.path, fileList)                           
            #print self
            self.handle = tarfile.open(name=self.file, mode=self.mode)
            extract()
        except Exception:            
            raise
        finally:
            if self.handle:
                self.handle.close()
                self.handle = None                    
    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None
        self.file = None        
        self.mode = None
        self.path = None
        self.folder = None
        self.skipFolder = None
    def setFile(self,str_filePath):
        self.file = str_filePath
    def setFolder(self,str_folderToExtract):
        self.folder = str_folderToExtract
    def setMode(self,str_mode):
        self.mode = str_mode
    def setPath(self, str_path):
        self.path = str_path
        
        
initialize()
