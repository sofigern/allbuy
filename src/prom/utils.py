from aiohttp.cookiejar import CookieJar
from http.cookies import SimpleCookie
import ujson


def dict_from_cookiejar(cj: CookieJar) -> dict:
    """Returns a key/value dictionary from a CookieJar.

    :param cj: CookieJar object to extract cookies from.
    :rtype: dict
    """

    cookie_dict = {cookie.key: cookie.value for cookie in cj if getattr(cookie, 'key', None)}
    return cookie_dict


def prepare_cookies(cookies_string: str) -> dict:
    cookies = {}
    
    for cookie_string in cookies_string.split(';'):
        cookie_data = ujson.loads(cookie_string)
        
        # Create a SimpleCookie object
        cookie = SimpleCookie()
        
        # Populate the SimpleCookie with data from the JSON
        cookie_name = cookie_data['name']
        cookie_value = cookie_data['value']
        cookie[cookie_name] = cookie_value
        
        # Set additional attributes if they exist
        if 'domain' in cookie_data:
            cookie[cookie_name]['domain'] = cookie_data['domain']
        if 'path' in cookie_data:
            cookie[cookie_name]['path'] = cookie_data['path']
        if 'expirationDate' in cookie_data:
            # Convert expiration date to a string format for SimpleCookie
            expires = int(cookie_data['expirationDate'])
            cookie[cookie_name]['expires'] = expires
        if 'secure' in cookie_data:
            cookie[cookie_name]['secure'] = cookie_data['secure']
        if 'httpOnly' in cookie_data:
            cookie[cookie_name]['httponly'] = cookie_data['httpOnly']
        
        # Add to the cookies dictionary
        cookies[cookie_name] = cookie_value
    
    return cookies