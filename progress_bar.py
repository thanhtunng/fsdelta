from alive_progress import alive_bar, showtime, show_bars, show_spinners
import time

def compute():
  for i in range(100):
    time.sleep(0.05)  # process items
    yield i  # insert this and you're done!

with alive_bar(100, bar="bubbles") as bar:
  for i in compute():
     bar()

# showtime()
# show_spinners()
# show_bars()
