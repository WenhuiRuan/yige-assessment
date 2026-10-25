import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.db import connect
from app.backend.tests.support import add, assert_error, db_state


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE skus SET price_minor=-1 WHERE id='sku-red-s'",
        "UPDATE skus SET price_minor=1.5 WHERE id='sku-red-s'",
        "UPDATE skus SET on_hand=-1 WHERE id='sku-red-s'",
        "UPDATE skus SET reserved=-1 WHERE id='sku-red-s'",
        "UPDATE skus SET reserved=on_hand+1 WHERE id='sku-red-s'",
        "UPDATE cart_items SET quantity=0",
        "UPDATE cart_items SET quantity=-1",
        "UPDATE carts SET revision=-1",
        "UPDATE inventory_meta SET revision=-1",
        "INSERT INTO inventory_meta VALUES (2, 0)",
        "INSERT INTO cart_items VALUES ('demo','not-a-sku',1)",
        "INSERT INTO cart_items VALUES ('missing','sku-red-s',1)",
        "INSERT INTO cart_items VALUES ('demo','sku-red-s',1)",
        "INSERT INTO skus VALUES ('another','p1','red','S',1,1,0,'/images/product.svg')",
        "INSERT INTO skus VALUES ('new','missing','red','S',1,1,0,'/images/product.svg')",
    ],
)
def test_sql_checks_foreign_keys_and_unique_constraints(
    client: TestClient, db_path: Path, sql: str
) -> None:
    assert add(client).status_code == 200
    before = db_state(db_path)
    with connect(db_path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(sql)
    assert db_state(db_path) == before


def test_protocol_upper_bounds_are_accepted_before_stock_validation(client: TestClient) -> None:
    assert_error(add(client, quantity=2147483647), 409, "INSUFFICIENT_STOCK")
    assert_error(add(client, sku="x" * 128), 404, "SKU_NOT_FOUND")
    assert add(client, key="x" * 128).status_code == 200
    assert add(client, key="!~").status_code == 200
