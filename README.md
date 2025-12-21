conda activate data_analysis
uv で管理。
推論コードを書いてそのコードのライブラリを出す。それだけdatasetに入れる。
data_analysisである程度kaggle内のライブラリは弾かれる。


## 新しい実験を作成する

```bash
make new NAME=hoge
```

### 生成される構造

```
experiments/exp013_hoge/
├── run.py
├── config.yaml
└── exp/
    └── 000.yaml
```

### 挙動

- 既存の最大番号を自動で検出し、次の番号を付与する  
- 番号の衝突は起きない  
- `input/` は作成されない  

---

## 実験を実行する

```bash
make run EXP=13
```

### 挙動

- `exp013_*` を自動で探索する  
- 対応するディレクトリ直下の `run.py` を実行する  
- 実験名を覚える必要はない  

---

## 実験一覧を表示する

```bash
make list
```


---

## 推奨運用フロー

```bash
make new NAME=baseline
make run EXP=14
```

実験は「作る → 実行する」を最短距離で回す。  
番号管理・再現性・事故防止をすべて Makefile に任せる。
```






