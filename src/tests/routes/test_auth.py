import pytest
from httpx import AsyncClient
from app.core.security.utils import Hash
from app.core.config import settings

@pytest.mark.asyncio
async def test_auth_login(
    test_async_client: AsyncClient,
    mock_mongo_db
) -> None:
    # Test data
    pwd = "md192859ncSDA" 
    hashed_password = Hash.hash(pwd)
    test_user = {
        "edbo_id": "19295829", 
        "password": hashed_password
    }

    # Insert test user into mock database
    a = await mock_mongo_db.users.insert_one(test_user)

    # Verify user was inserted
    user = await mock_mongo_db.users.find_one({"edbo_id": test_user["edbo_id"]})
    assert user is not None
    assert user["edbo_id"] == test_user["edbo_id"]

    # Test login endpoint
    response = await test_async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={
            "username": test_user["edbo_id"], 
            "password": pwd
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "token_type" in response.json()
    assert response.json()["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_auth_login_invalid_credentials(
    test_async_client: AsyncClient,
    mock_mongo_db
) -> None:
    # Test with invalid credentials
    response = await test_async_client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={
            "username": "nonexistent", 
            "password": "wrongpassword"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    assert response.status_code == 401

# from httpx import AsyncClient
# import pytest


# from app.core.security.utils import Hash  

# from app.core.config import settings

# @pytest.mark.asyncio
# async def test_auth_login(
#   test_async_client: AsyncClient,
#   mock_mongo_db
# ) -> None:
#     pwd = "md192859ncSDA" 
#     credentials = {"edbo_id": "19295829", "password": Hash.hash(pwd)}

#     await mock_mongo_db.users.insert_one(credentials)

#     print(await mock_mongo_db.users.find_one({"edbo_id": credentials["edbo_id"]}))

#     response = await test_async_client.post(
#         f"{settings.API_V1_STR}/auth/login",
#         data={"username": credentials["edbo_id"], "password": pwd},
#         headers={"Content-Type": "application/x-www-form-urlencoded"},)
#     # print(response.content)
#     assert response.status_code == 200