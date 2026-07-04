# seeds.md — ANN corpus seed list (~55 papers)

> Grouped by family. Ingestion resolves each title to a Semantic Scholar paperId
> via title search. Titles + years are enough; exact IDs are looked up at fetch time.
> ✅ = anchor, verified title/author/year. Others are real fill-in candidates — if
> S2 title search returns no/wrong match, drop or swap. Target: ~55 landed with abstracts.

## Family 1 — Foundations / dimensionality wall
- ✅ Approximate Nearest Neighbors: Towards Removing the Curse of Dimensionality — Indyk, Motwani — 1998 (STOC)
- A quantitative analysis and performance study for similarity-search methods in high-dimensional spaces — Weber, Schek, Blott — 1998 (VLDB)
- Multidimensional binary search trees used for associative searching (KD-trees) — Bentley — 1975
- When Is "Nearest Neighbor" Meaningful? — Beyer, Goldstein, Ramakrishnan, Shaft — 1999
- Scalable Nearest Neighbor Algorithms for High Dimensional Data (FLANN) — Muja, Lowe — 2014 (TPAMI)

## Family 2 — Hashing / LSH
- ✅ Approximate Nearest Neighbors: Towards Removing the Curse of Dimensionality — Indyk, Motwani — 1998 (also LSH origin)
- ✅ Multi-Probe LSH: Efficient Indexing for High-Dimensional Similarity Search — Lv, Josephson, Wang, Charikar, Li — 2007 (VLDB)
- Locality-Sensitive Hashing Scheme Based on p-Stable Distributions — Datar, Immorlica, Indyk, Mirrokni — 2004 (SoCG)
- Similarity Estimation Techniques from Rounding Algorithms (SimHash) — Charikar — 2002 (STOC)
- Near-Optimal Hashing Algorithms for Approximate Nearest Neighbor in High Dimensions — Andoni, Indyk — 2008
- A Survey on Learning to Hash — Wang, Zhang, Song, Sebe, Shen — 2018 (TPAMI)
- b-Bit Minwise Hashing — Li, König — 2010 (WWW)

## Family 3 — Quantization / compression
- ✅ Product Quantization for Nearest Neighbor Search — Jégou, Douze, Schmid — 2011 (TPAMI)
- ✅ Optimized Product Quantization — Ge, He, Ke, Sun — 2013 (CVPR)
- ✅ Locally Optimized Product Quantization for Approximate Nearest Neighbor Search — Kalantidis, Avrithis — 2014 (CVPR)
- Additive Quantization for Extreme Vector Compression — Babenko, Lempitsky — 2014 (CVPR)
- Iterative Quantization: A Procrustean Approach to Learning Binary Codes (ITQ) — Gong, Lazebnik, Gordo, Perronnin — 2013 (TPAMI)
- Cartesian k-means — Norouzi, Fleet — 2013 (CVPR)
- Aggregating Local Image Descriptors into Compact Codes — Jégou, Perronnin, Douze, Sánchez, Pérez, Schmid — 2012 (TPAMI)
- Low-Precision Quantization for Efficient Nearest Neighbor Search — Ko, Keivanloo, Lakshman, Schkufza — 2021

## Family 4 — Inverted-file / partitioning
- ✅ The Inverted Multi-Index — Babenko, Lempitsky — 2012 (CVPR)
- ✅ Revisiting the Inverted Indices for Billion-Scale Approximate Nearest Neighbors — Baranchuk, Babenko, Malkov — 2018 (ECCV)
- Searching in One Billion Vectors: Re-rank with Source Coding — Jégou, Tavenard, Douze, Amsaleg — 2011 (ICASSP)

## Family 5 — Graph-based (densest cluster)
- ✅ Scalable Distributed Algorithm for Approximate Nearest Neighbor Search in High Dimensional General Metric Spaces (NSW) — Malkov, Ponomarenko, Logvinov, Krylov — 2012 (SISAP)
- ✅ Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs (HNSW) — Malkov, Yashunin — 2016 (arXiv) / 2020 (TPAMI)
- ✅ Fast Approximate Nearest Neighbor Search With The Navigating Spreading-out Graph (NSG) — Fu, Xiang, Wang, Cai — 2019 (VLDB)
- ✅ EFANNA: An Extremely Fast Approximate Nearest Neighbor Search Algorithm Based on kNN Graph — Fu, Cai — 2016
- A Comprehensive Survey and Experimental Comparison of Graph-Based Approximate Nearest Neighbor Search — Wang, Xu, Yue, Wang — 2021
- ✅ Down with the Hierarchy: The 'H' in HNSW Stands for "Hubs" (FlatNav) — Coleman et al. — 2024 (good CHALLENGES edge vs HNSW)

## Family 6 — Disk / billion-scale / production
- ✅ DiskANN: Fast Accurate Billion-point Nearest Neighbor Search on a Single Node — Subramanya, Devvrit, Kadekodi, Krishnaswamy, Simhadri — 2019 (NeurIPS)
- ✅ Billion-Scale Similarity Search with GPUs (FAISS-GPU) — Johnson, Douze, Jégou — 2019/2021 (IEEE Big Data)
- Accelerating Large-Scale Inference with Anisotropic Vector Quantization (ScaNN) — Guo, Sun, Lindgren, Geng, Simcha, Chern, Kumar — 2020 (ICML)
- BANG: Billion-Scale Approximate Nearest Neighbor Search Using a Single GPU — Karthik, Khan, Singh, Simhadri, Vedurada — 2024
- SPANN: Highly-efficient Billion-scale Approximate Nearest Neighbor Search — Chen et al. — 2021 (NeurIPS)

## Family 7 — Benchmarks / surveys (connective tissue)
- ✅ ANN-Benchmarks: A Benchmarking Tool for Approximate Nearest Neighbor Algorithms — Aumüller, Bernhardsson, Faithfull — 2020 (Information Systems)
- ✅ Results of the NeurIPS'21 Challenge on Billion-Scale Approximate Nearest Neighbor Search — Simhadri et al. — 2022
- Approximate Nearest Neighbor Search on High Dimensional Data — Experiments, Analyses, and Improvement — Li, Zhang, Sun, Chen, Zhang, Lin — 2020 (TKDE)
