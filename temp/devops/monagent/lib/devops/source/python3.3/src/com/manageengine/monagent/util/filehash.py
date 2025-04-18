# $Id$

import collections
import os
import hashlib
import glob

from com.manageengine.monagent.logger import AgentLogger

_ALGORITHM_MAP = {
    'sha256' : hashlib.sha256,
    'sha512' : hashlib.sha512,
}

FileHashResult = collections.namedtuple("FileHashResult", ["filename", "hash"])

SUPPORTED_ALGORITHMS = set(_ALGORITHM_MAP.keys())

class FileHash:
    def __init__(self, hash_algorithm='sha256', chunk_size=4096):
        AgentLogger.log(AgentLogger.STDOUT,'hash initialised')
        self.chunk_size = chunk_size
        self.hash_algorithm = hash_algorithm

    def hash_file(self, filename):
        with open(filename, mode="rb", buffering=0) as fp:
            hash_func = _ALGORITHM_MAP[self.hash_algorithm]()
            buffer = fp.read(self.chunk_size)
            while len(buffer) > 0:
                hash_func.update(buffer)
                buffer = fp.read(self.chunk_size)
        return hash_func.hexdigest()

    def hash_files(self, filenames):
        return [FileHashResult(fname, self.hash_file(fname)) for fname in filenames]

    def hash_dir(self, path, pattern='*'):
        saved_dir = os.getcwd()
        os.chdir(os.path.abspath(path))
        filenames = [filename for filename in glob.glob(pattern) if os.path.isfile(filename)]
        result = self.hash_files(filenames)
        os.chdir(saved_dir)
        return result
    
    def hash_string(self,content):
        hash_func = _ALGORITHM_MAP[self.hash_algorithm](content.encode())
        return hash_func.hexdigest()
    
    def verify_hash(self,expected_hash_value,file_to_verify):
        hash_result = False
        actual_hash_value = self.hash_file(file_to_verify)
        if expected_hash_value == actual_hash_value:
            hash_result = True
        return hash_result,actual_hash_value
        