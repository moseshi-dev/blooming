# 使用の準備
constants.sample.pyをコピーし、各値を適切に書き換える。
```console
cp constants.sample.py constants.py
# edit constants.py
```
dictionary.sample.csvをコピーし、読み替え内容を記載する
```console
cp dictionary.sample.csv dictionary.csv
# 例
echo "読み方,よみかた" >> dictionary.csv
```
依存ライブラリをインストールし、起動。
```console
pip install -r requirements.txt
python Mintbot.py
```
