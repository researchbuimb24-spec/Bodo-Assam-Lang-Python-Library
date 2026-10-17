import sqlite3

c = sqlite3.connect("data/lexicon.sqlite")
q = "select word, freq from words where word between 'a' and 'zzzz'"
print("Random 40:", c.execute(q + " order by random() limit 40").fetchall())
print("Top 40:", c.execute(q + " order by freq desc limit 40").fetchall())
