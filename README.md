# Gnucash to Ledger

Convert Gnucash files to ledger file format. Supports arbitrary decimal places.

## Install requirements

Clone the project

```
git clone https://github.com/lodenrogue/gnucash-to-ledger
```

Change into the gnucash-to-ledger directory

```
cd gnucash-to-ledger
```

Copy your gnucash file to the current directory

```
cp myfile.gnucash .
```

Install python requirements

```
pip install -r requirements.txt
```

## How to run

The script takes a required gnucash file as the first argument and an optional output file. 
If no output is given the output will be redirected to stdout.
If a file already exists with the same name as output file nothing is written.

```
python3 gnucash2ledger.py gnucash_file.gnucash output
```

## Optional: Make the script executable

Make script executable

```
chmod +x gnucash2ledger.py
```

You can now add it to your PATH so its usable anywhere

---


Original code source found here: https://gist.github.com/nonducor/ddc97e787810d52d067206a592a35ea7/
