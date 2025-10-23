import os
from natsort import natsorted

dir = os.path.abspath(r"Z:\ssd\movie\blends")

items = os.listdir(dir)
sorted_items = natsorted(items)

for item in sorted_items:
    print(item)