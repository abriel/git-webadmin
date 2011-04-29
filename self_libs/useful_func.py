import os

def rmall(dirPath):                             # delete dirPath and below
	namesHere = os.listdir(dirPath)
	for name in namesHere:                      # remove all contents first
		path = os.path.join(dirPath, name)
		if not os.path.isdir(path):             # remove simple files
			os.remove(path)
		else:                                   # recur to remove subdirs
			rmall(path)
	os.rmdir(dirPath)                           # remove now-empty dirPath

