// /api -> the developer docs. (/api/subscribe and /api/v1/* have their own handlers.)
export const onRequest = ({ request }) => Response.redirect(new URL("/developers/", request.url).href, 301);
