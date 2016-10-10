var http = require('http-status-codes');

var Log;
function Auth(app) {
  this.app = app;
  Log = app.log;
}
module.exports = Auth;

module.exports.authenticatedOr404 = function (req, res, next) {
  if (req.session.userId) {
    return next();
  }

  Log.info("No session userId");
  res.sendStatus(http.NOT_FOUND);
};

module.exports.authenticatedOrRedirect = function (req, res, next) {
  if (req.session.userId)
    return next();

  res.redirect('/');
};
