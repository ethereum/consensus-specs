# Shuffling Test Generator

```
2018 Status Research & Development GmbH
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).

This work uses public domain work under CC0 from the Ethereum Foundation
https://github.com/ethereum/eth2.0-specs
```


This file implements a test vectors generator for the shuffling algorithm described in the Ethereum
[specs](https://github.com/ethereum/eth2.0-specs/blob/2983e68f0305551083fac7fcf9330c1fc9da3411/specs/core/0_beacon-chain.md#get_new_shuffling)

Utilizes 'swap or not' shuffling found in [An Enciphering Scheme Based on a Card Shuffle](https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf).  
See the `Generalized domain` algorithm on page 3.
