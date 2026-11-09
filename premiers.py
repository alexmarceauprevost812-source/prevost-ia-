def est_premier(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def main():
    trouves = 0
    n = 2
    while trouves < 10:
        if est_premier(n):
            print(n)
            trouves += 1
        n += 1


if __name__ == "__main__":
    main()
