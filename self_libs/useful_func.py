import os

################################################################
# Use: "python rmall.py directoryPath directoryPath..."
# recursive directory tree deletion: removes all files and
# directories at and below directoryPaths; recurs into subdirs
# and removes parent dir last, because os.rmdir requires that
# directory is empty; like a Unix "rm -rf directoryPath"
################################################################
# Taken from http://codeidol.com/python/python3/System-Examples-Directories/Deleting-Directory-Trees/
################################################################

def rmall(dirPath):                             # delete dirPath and below
	namesHere = os.listdir(dirPath)
	for name in namesHere:                      # remove all contents first
		path = os.path.join(dirPath, name)
		if not os.path.isdir(path):             # remove simple files
			os.remove(path)
		else:                                   # recur to remove subdirs
			rmall(path)
	os.rmdir(dirPath)                           # remove now-empty dirPath

