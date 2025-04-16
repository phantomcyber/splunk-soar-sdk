const fs = require("fs");

function getReleaseVersion() {
  if (fs.existsSync("release_version.txt")) {
    return fs.readFileSync("release_version.txt").toString().trim();
  }
  return null;
}

async function uploadReleaseArtifacts({ github, context }) {
  const tag = getReleaseVersion();
  if (!tag) {
    console.log("This change did not result in a release.");
    return
  }

  const { owner, repo } = context.repo;

  const artifacts = fs
    .readdirSync("dist")
    .filter((f) => f.endsWith(".whl") || f.endsWith(".tar.gz"));
  const getRelease = await github.rest.repos.getReleaseByTag({
    owner,
    repo,
    tag,
  });
  const release_id = getRelease.data.id;

  artifacts.forEach((name) => {
    const data = fs.readFileSync(`dist/${name}`);
    github.rest.repos.uploadReleaseAsset({
      owner,
      repo,
      release_id,
      name,
      data,
    });
  });
}

function commentReleaseNotes({ github, context }) {
  const versionNumber = getReleaseVersion();
  if (!versionNumber) {
    return github.rest.issues.createComment({
      issue_number: context.issue.number,
      owner: context.repo.owner,
      repo: context.repo.repo,
      body: "Merging this PR will not result in a release.",
    });
  }

  const releaseNotes = fs.readFileSync("release_notes.txt").toString().trim();

  const commentBody = `Merging this PR will release \`${versionNumber}\` with the following release notes:\n\n${releaseNotes}`;

  return github.rest.issues.createComment({
    issue_number: context.issue.number,
    owner: context.repo.owner,
    repo: context.repo.repo,
    body: commentBody,
  });
}

module.exports = { uploadReleaseArtifacts, commentReleaseNotes };
