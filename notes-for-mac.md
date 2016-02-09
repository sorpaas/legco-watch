
# Dependencies

```
brew install postgresql graphviz
brew install libxml2
brew install libxslt
brew install libmagic
brew link libxml2 --force
brew link libxslt --force
```

```
env LDFLAGS="-L$(brew --prefix openssl)/lib" CFLAGS="-I$(brew --prefix openssl)/include" pip install cryptography
```

## Database

```
app/legcowatch/local.py
```

## Test Env Setup

Init and migrate DB to the latest status:

```
python manage.py syncdb
python manage.py schemamigration raw --auto
python manage.py migrate raw
```

Test scraping member profile from legco library:

```
python manage.py shell
import raw.tasks
raw.tasks.do_scrape('library_member')
```

Test processing scraped member profile from legco library:

```
python manage.py shell
import raw.tasks
raw.tasks.process_scrape('library_member')
```

## References

* http://stackoverflow.com/questions/19548011/cannot-install-lxml-on-mac-os-x-10-9

