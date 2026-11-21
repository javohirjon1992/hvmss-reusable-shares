/* GMP reference for Horner evaluation. Input: q, x, length, then
   coefficients from highest degree to constant (decimal integers). */
#include <gmp.h>
#include <stdio.h>
int main(void) {
    mpz_t q, x, y, c;
    unsigned count;
    mpz_inits(q, x, y, c, NULL);
    if (gmp_scanf("%Zd %Zd %u", q, x, &count) != 3 || mpz_sgn(q)<=0) return 1;
    for (unsigned i=0; i<count; ++i) {
        if (gmp_scanf("%Zd", c)!=1) return 1;
        mpz_mul(y,y,x);
        mpz_add(y,y,c);
        mpz_mod(y,y,q);
    }
    gmp_printf("%Zd\n",y);
    mpz_clears(q,x,y,c,NULL);
    return 0;
}
