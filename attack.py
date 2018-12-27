import os
import statistics as st
import multiprocessing

ns = []

def parse(fn):
    with open(fn, "r") as f:
        l = f.readline()
        n = int(l)
        ns.append(n)

def compute(k):
    for i in range(n):
        name = "tmp_{k}.txt".format(k=k)
        command = "R={r} N=100 K={k} ./attack > {name}".format(r=r, k=k, name=name)
        os.system(command)
        parse(name)
    print("{},{},{},{},{}".format(k, r, st.mean(ns), st.stdev(ns), st.median(ns)))

ratio = [x * 0.01 for x in range(51, 100)]
for idx, r in enumerate(ratio):
    ns.clear()
    n = 1000
    p = multiprocessing.Pool(processes=8)
    for k in range(3, 11):
        p.apply_async(compute, args=(k,))
    p.close()
    p.join()
