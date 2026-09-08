"""Read-only MongoDB connectivity probe; does not print secrets or records."""
import asyncio

from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError

from app.db.mongo import mongo_database


async def check() -> int:
    try:
        async with mongo_database() as database:
            await database.command("ping")
            # Verify authenticated access to the selected DB, without reading
            # documents or listing databases outside the requested scope.
            names = await database.list_collection_names()
            print(f"MongoDB connected. Database: {database.name}. Collections: {len(names)}.")
        return 0
    except OperationFailure as exc:
        print(f"MongoDB authentication/access failed (code={exc.code}). Check database user permissions.")
    except ConfigurationError:
        print("MongoDB configuration/DNS failed. Check the Atlas cluster hostname and connection URI.")
    except PyMongoError:
        print("MongoDB connection failed. Check cluster availability, TLS, network and Atlas IP access list.")
    except ValueError:
        print("MongoDB settings are missing or invalid. Check MONGODB_URL and MONGODB_DATABASE in .env.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
