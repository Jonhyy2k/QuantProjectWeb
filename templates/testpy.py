import time

fib_cache = {}

def fib_numbers(n):
    
    
    if n in fib_cache:
        return fib_cache[n]
    
    if n == 0:
        fib_cache[n] = 0
        return 0
    if n == 1:
        fib_cache[n] = 1
        return 1

    fib_cache[n] = fib_numbers(n-1) + fib_numbers(n-2)
    return fib_cache[n]

n = int(input("Enter the position of the Fibonacci sequence (n): "))

start_time = time.time()
print(fib_numbers(n))
print("Time Taken:", time.time() - start_time)