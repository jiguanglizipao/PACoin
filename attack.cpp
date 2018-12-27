#include <stdio.h>
#include <random>
#include <vector>
#include <algorithm>
#include <stdlib.h>

using namespace std;

int gcounter = 0;

int ecounter = gcounter;

unsigned th = (unsigned)std::pow(2, 16);

std::vector<std::mt19937> mts;

bool* isEvil;

int main() {
    int n = 100;
    const char* env = getenv("N");
    if (env != NULL) {
        n = atoi(env);
    }

    int k = 1;
    env = getenv("K");
    if (env != NULL) {
        k = atoi(env);
    }

    double ratio = 0.3;
    env = getenv("R");
    if (env != NULL) {
       ratio = atof(env); 
    }

    int en = int(n * ratio);
    isEvil = new bool[n];
    for (int i = 0; i < n; ++i) {
        if (i < en) isEvil[i] = true;
        else isEvil[i] = false;
    }
    
    std::random_device rd;
    std::shuffle(isEvil, isEvil + n, rd);
    std::shuffle(isEvil, isEvil + n, rd);
    std::shuffle(isEvil, isEvil + n, rd);

    for (int i = 0; i < n; ++i) {
        mts.push_back(std::mt19937(rd()));
    }

    std::uniform_int_distribution<unsigned int> dis;
    bool to_exit = false;
    while (!to_exit) {
        for (int i = 0; i < n; ++i) {
            unsigned tmp = dis(mts[i]);
            if (tmp > th) {
                if (isEvil[i]) {
                    // evil
                    ++ecounter;
                    if (ecounter >= gcounter + k) {
                        printf("%d\n", ecounter);
                        to_exit = true;
                        break;
                    }
                } else {
                    ++gcounter;
                }
            }
        }
    }
        
    delete[] isEvil;
    return 0;
}
