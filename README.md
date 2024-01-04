# pixiv-spider
Download pixiv images/Gifs with custom settings...

## Requirements

- API: https://github.com/upbit/pixivpy
- Get refresh_token (selenium):
  - `python pixiv_auth.py login`

## Usages

*Downloaded images(info) are stored in `./cache`. Use `--cache ./cache --update-cache` to skip.*

**Download by keyword**

```shell
python main.py key -i Griseo -d ./pixiv --cache ./cache --update-cache
```

**Download by user_id**

```shell
python main.py usr -i 14801956 -d ./pixiv --cache ./cache --update-cache
```

**Download by `key.py`**

```shell
python main.py key -d ./pixiv --cache ./cache --update-cache
```

**Download by `usr.py`**

```shell
python main.py usr -d ./pixiv --cache ./cache --update-cache
```

**Auto restart**

```shell
python auto_runner.py -c "python main.py key -d ./pixiv --cache ./cache --update-cache"
```

## Utils

**Delete unfinished images**

```shell
python main.py clean -d ./pixiv
```

**Update search file**

```shell
python main.py update-key -d ./pixiv
python main.py update-usr -d ./pixiv --input-dir .
```

**Update cache**

```shell
python main.py update-cache -d ./pixiv --cache ./cache
```

