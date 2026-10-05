# Migrate and run this project

This file is for a Cursor agent on a new Mac. Follow it in order and stop if a step fails. Do not invent database contents, API keys, or `settings.php`. If a required local file is missing, ask the user for it.

Today's pull branch is **`2026-10-05`**.

## What has to be running

| Piece | Where | What it is |
|---|---|---|
| Drupal CMS | `/Applications/MAMP/htdocs/myresearch2` | This repo, branch `2026-10-05` |
| Python worker | `/Applications/MAMP/htdocs/story-pipeline-worker` | Separate repo. Drupal launches this path |
| MySQL database | database `myresearch` on `127.0.0.1:8889` | Not in git. Import a dump from the old Mac |
| Story Studio | `story-studio/` inside this repo | Optional Next.js app on port 3000 |
| Automation engine | `/Users/averma/project/research-story-17thmay-automation` | Needed only to run story jobs, not to open the CMS |

MAMP on the old Mac uses Apache **8888** and MySQL **8889**. Keep those ports. The CMS URL is `http://localhost:8888/myresearch2/web`.

## 1. Install tools

Install [MAMP](https://www.mamp.info/) and set:

- Apache port `8888`
- MySQL port `8889`

Start MAMP servers before the database and Drupal steps.

Also install, if they are not already on the machine:

- Git
- Composer (`composer`)
- Node.js 20 or newer and npm
- Python 3
- AWS CLI only if the user is copying the database dump from S3

Use MAMP's PHP 8.3 for Composer and Drush:

```bash
export PATH="/Applications/MAMP/bin/php/php8.3.14/bin:/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
php -v
```

PHP must be 8.1 or newer. If `php8.3.14` is not the folder name on this MAMP install, use the newest `php8.3*` or `php8.4*` directory under `/Applications/MAMP/bin/php/`.

## 2. Clone the code

```bash
git clone -b 2026-10-05 git@github.com:wework1988/cms-code.git /Applications/MAMP/htdocs/myresearch2

git clone -b 2026-10-05 git@github.com:wework1988/cms-python-story-worker.git /Applications/MAMP/htdocs/story-pipeline-worker
```

Both repos use branch `2026-10-05`. The worker branch is the existing worker code with no new commit. Its only uncommitted local file was an API-key pool, and that file stays off git.

Put both folders at those exact paths. `WorkerLauncher.php` defaults to `/Applications/MAMP/htdocs/story-pipeline-worker`.

## 3. Import the database

The dump is not in git. The user must supply `myresearch.sql` from the old Mac (or from their private S3 backup).

```bash
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"

mysql -uroot -proot -h127.0.0.1 -P8889 \
  -e "CREATE DATABASE IF NOT EXISTS myresearch CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"

mysql -uroot -proot -h127.0.0.1 -P8889 myresearch < /path/to/myresearch.sql
```

MAMP's default MySQL user is `root` with password `root`.

## 4. Local files that git does not contain

Create these on the new Mac. Do not commit them.

### Drupal settings

`web/sites/default/settings.php` is gitignored. Copy it from the old Mac if the user has it. If not, create it from the Drupal default and point it at the database:

```bash
cd /Applications/MAMP/htdocs/myresearch2
cp web/sites/default/default.settings.php web/sites/default/settings.php
chmod 644 web/sites/default/settings.php
```

Append this to the bottom of `settings.php`. Generate a new `hash_salt` with `php -r "echo bin2hex(random_bytes(32)), PHP_EOL;"` if the copied file does not already have one.

```php
$settings['hash_salt'] = 'PUT_A_LONG_RANDOM_STRING_HERE';

$databases['default']['default'] = [
  'database' => 'myresearch',
  'username' => 'root',
  'password' => 'root',
  'prefix' => '',
  'host' => '127.0.0.1',
  'port' => '8889',
  'isolation_level' => 'READ COMMITTED',
  'driver' => 'mysql',
  'namespace' => 'Drupal\\mysql\\Driver\\Database\\mysql',
  'autoload' => 'core/modules/mysql/src/Driver/Database/mysql/',
];
```

Uploaded images live in `web/sites/default/files`, which is also gitignored. Copy that folder from the old Mac only if the user needs existing media. The site still opens without it.

### Worker environment

```bash
cd /Applications/MAMP/htdocs/story-pipeline-worker
cp .env.example .env
```

Edit `.env`:

```env
DRUPAL_BASE_URL=http://localhost:8888/myresearch2/web
DRUPAL_API_KEY=
AUTOMATION_REPO=/Users/averma/project/research-story-17thmay-automation
STORY_ASSET_ROOT=/Users/averma/project/research-story-17thmay-automation/cms-generate-stories
```

Get `DRUPAL_API_KEY` after Drupal is running:

```bash
cd /Applications/MAMP/htdocs/myresearch2
export PATH="/Applications/MAMP/bin/php/php8.3.14/bin:/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
vendor/bin/drush story-pipeline:info
```

Paste that key into the worker `.env`. Do not put the key in git.

There is a second copy of the worker inside this repo at `story-pipeline-worker/`. Drupal does not launch that copy. Leave it. The live worker is the folder next to `myresearch2`.

### Story Studio environment

Only if the user wants Story Studio:

```bash
cd /Applications/MAMP/htdocs/myresearch2/story-studio
cp .env.example .env
```

Put the user's DeepSeek or OpenAI key in `.env`. An empty key still allows the demo project. Story Studio's SQLite file `prisma/dev.db` is not in git. A fresh migrate creates an empty database. Copy `prisma/dev.db` from the old Mac only to keep existing Story Studio projects.

## 5. Install dependencies

```bash
export PATH="/Applications/MAMP/bin/php/php8.3.14/bin:$PATH"

cd /Applications/MAMP/htdocs/myresearch2
composer install

cd /Applications/MAMP/htdocs/story-pipeline-worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

`composer install` installs Drupal core, Drush, `admin_toolbar`, and `diff` into `web/core`, `vendor`, and `web/modules/contrib`. Those folders are not committed.

Story Studio:

```bash
cd /Applications/MAMP/htdocs/myresearch2/story-studio
npm install
npx prisma migrate dev
npm run db:seed
```

## 6. Automation repo, only for story jobs

Opening the CMS does not need this. Running storyboard or generate-story does. The worker calls `deepseek_pipeline.py` inside this repo.

```bash
git clone git@github.com:wework1988/story-automation-updated.git /Users/averma/project/research-story-17thmay-automation
cd /Users/averma/project/research-story-17thmay-automation
git checkout 2026-08-12-step0-scene-structure
```

If the Mac username is not `averma`, clone it somewhere else and change `AUTOMATION_REPO` and `STORY_ASSET_ROOT` in the worker `.env` to that path. Also set the Drupal worker path if the worker is not at `/Applications/MAMP/htdocs/story-pipeline-worker`. That setting is stored in the database at `admin/config/content/story-pipeline`.

Generated story folders under `cms-generate-stories` are local output. They are not required to boot the site. Copy them from the old Mac only to keep old scripts and audio.

## 7. Start and verify

1. MAMP Apache and MySQL are running.
2. Open `http://localhost:8888/myresearch2/web`.
3. Log in with the Drupal account from the imported database. Do not create a new install.
4. Open `http://localhost:8888/myresearch2/web/admin/config/content/story-pipeline` and confirm the worker path exists.
5. Confirm the worker can see Drupal:

```bash
cd /Applications/MAMP/htdocs/story-pipeline-worker
./run.sh help
```

6. Story Studio, in a separate terminal:

```bash
cd /Applications/MAMP/htdocs/myresearch2/story-studio
npm run dev
```

Open `http://localhost:3000`.

## If something fails

- Drupal white screen or database error: MySQL is not on port 8889, or `settings.php` does not match the import.
- `composer install` uses the wrong PHP: put MAMP's PHP 8.3 first on `PATH`, then run it again.
- Worker says the path does not exist: the clone is not at `/Applications/MAMP/htdocs/story-pipeline-worker`.
- Worker says the API key is missing: run `vendor/bin/drush story-pipeline:info` and copy the key into the worker `.env`.
- Story jobs fail before any LLM call: the automation repo is missing, or `AUTOMATION_REPO` points at the wrong folder.
