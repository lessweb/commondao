# commondao

## How to install commondao?

```bash
pip install commondao
```

## How to use commondao?

```python
import toml
import commondao

config = {
    'host': '****',
    'port': 3306,
    'user': '****',
    'password': '****',
    'db': '****',
    'autocommit': True,
}
async with commondao.connect(**config) as db:
    await db.save('tbl_user', {'id': 1, 'name': 'John Doe'})
    user = await db.get_by_key_or_fail('tbl_user', key={'id': 1})
    print(user['name'])  # Output: John Doe

```
