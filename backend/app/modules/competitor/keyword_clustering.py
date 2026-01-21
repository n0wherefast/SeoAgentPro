# app/modules/competitor/keyword_clustering.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from typing import List
import numpy as np

def cluster_keywords(keywords: List[str], n_clusters: int = 5):
    """
    keywords: lista di keyword/testo (short phrases)
    Ritorna: mapping cluster_id -> [keywords], centroids (top terms)
    """
    if not keywords:
        return {"clusters": {}, "centroids": []}

    # TF-IDF su keywords come documents
    vect = TfidfVectorizer(ngram_range=(1,2), min_df=1)
    X = vect.fit_transform(keywords)

    # num cluster safe
    k = min(n_clusters, max(1, int(len(keywords)/2)))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X)

    clusters = {}
    for idx, label in enumerate(kmeans.labels_):
        clusters.setdefault(int(label), []).append(keywords[idx])

    # Centroids: top features per cluster centroid
    centroids = []
    terms = np.array(vect.get_feature_names_out())
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    for i in range(k):
        top_terms = [terms[ind] for ind in order_centroids[i, :5] if ind < len(terms)]
        centroids.append(top_terms)

    return {"clusters": clusters, "centroids": centroids}
