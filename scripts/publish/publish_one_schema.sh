proj=$1
esgvoc use "$proj@latest"
ver=`python scripts/publish/get_schema_version.py $proj`
echo $ver

branch=$(git branch --show-current)
git checkout gh-pages
pushd $proj
esgvoc schema $proj -o schema.json

if [ ! -d $ver ] ; then
    mkdir $ver
    mv schema.json $ver
    git add $ver
    git commit -m"updating $proj to $ver" 
else
    res=`diff schema.json | wc -l`
    if [ $res ] ; then
	echo  "Schemas differ for $project/$ver"
    else
       echo  "Matching schemas $project/$ver"
    fi
fi
popd

git checkout $branch
