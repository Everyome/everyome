from everyome_c_community_kmer_spectrum.engine import count


def test_counts_overlapping_kmers():
    c = count(["ACGTACGT", "NNACG"], 3)
    assert c["ACG"] == 3 and c["CGT"] == 2 and "NNA" not in c
