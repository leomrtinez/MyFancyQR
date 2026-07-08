# MyFancyQR

My Fancy QR is a 

## 📥 Instalation 

```bash 
git clone git@github.com:leomrtinez/MyFancyQR.git
```

## 📖 Requirment 

if you already have a conda environment : 

```bash 
conda install conda-forge::qrcode
```
your python environment will need the following requirment 


|     Name     |    Version   |
|--------------|--------------|
|`qrcode`      | 8.2          |
|`pyyaml`      | 6.0.3        |
|`pillow`      | 12.2.0       |
|


## ⚙️ Configuration 


|      args                  | default  |    comment                        |
|----------------------------|----------|-----------------------------------|
| `url`                      | –        | Text or URL to encode [required]  |
| `output`                   | "qrcode" | Output file path                  |
| `--list-formats`           | —        | list format                       |
| `-f`, `--format`           | .png     | format: blabla                    |
| `-bw`, `--border-width`    | 2        | border width: blabla              |
| `-bs`, `--box-size`        | 10       | box size: blabla                  |


## 🚀 Run 

```bash 
python main.py
```