var source = "bitmex";
var dest = "bitmex_pre";
var colls = db.getSiblingDB(source).getCollectionNames();
for (var i = 0; i < colls.length; i++) {
var from = source + "." + colls[i];
var to = dest + "." + colls[i];
db.adminCommand({renameCollection: from, to: to});
}